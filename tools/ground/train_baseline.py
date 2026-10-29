"""Reproducible RDD2022 D40 baseline. Not a validated navigation detector.

Frozen ImageNet MobileNetV2 features + trainable center-grid probability/box head.
The center variant uses alpha 0.35; the fpn variant uses multi-scale alpha 0.5 features.
No third-party serialized executable model is loaded. Official Keras HDF5 backbone only.
Exports one float32 TFLite tensor [1,20,20,5]: score, dx, dy, normalized width, height.
"""
import argparse, hashlib, io, json, os, pathlib, re, time, zipfile
import xml.etree.ElementTree as ET
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow import keras

SIZE, GRID, SEED = 320, 20, 4217

def letterbox(image):
    image = image.convert('RGB'); width, height = image.size
    scale = min(SIZE/width, SIZE/height)
    rw, rh = round(width*scale), round(height*scale)
    left, top = (SIZE-rw)//2, (SIZE-rh)//2
    canvas = Image.new('RGB', (SIZE,SIZE), (114,114,114))
    canvas.paste(image.resize((rw,rh), Image.Resampling.BILINEAR), (left,top))
    return np.asarray(canvas, np.float32)/127.5-1, (rw/width, rh/height, left, top)

def read_records(archive):
    records=[]; seen={}
    for name in sorted(archive.namelist()):
        if '/train/' not in name or not name.endswith('.xml'): continue
        root=ET.fromstring(archive.read(name)); width=int(root.findtext('size/width')); height=int(root.findtext('size/height'))
        if width<=0 or height<=0: continue
        stem=pathlib.PurePosixPath(name).stem; country=name.split('/')[0]
        image=f'{country}/train/images/{stem}.jpg'
        info=archive.getinfo(image)
        # Group adjacent source image numbers to reduce nearby-frame leakage, not a location-disjoint claim.
        group=f'{country}:{int(re.search(r"(\d+)$",stem)[1])//100}'
        split_hash=int(hashlib.sha256(f'{SEED}:{group}'.encode()).hexdigest()[:8],16)%100
        split='train' if split_hash<70 else 'validation' if split_hash<85 else 'test'
        signature=(info.CRC,info.file_size)
        if signature in seen: continue
        seen[signature]=image
        boxes=[]; ignored=[]
        for obj in root.findall('object'):
            if obj.findtext('name')!='D40': continue
            b=obj.find('bndbox')
            box=[max(0,float(b.findtext('xmin'))-1),max(0,float(b.findtext('ymin'))-1),
                 min(width,float(b.findtext('xmax'))),min(height,float(b.findtext('ymax')))]
            if box[2]<=box[0] or box[3]<=box[1]: continue
            (ignored if obj.findtext('difficult','0')=='1' else boxes).append(box)
        records.append(dict(id=stem,image=image,width=width,height=height,boxes=boxes,ignored=ignored,
                            group=group,split=split,crc32=f'{info.CRC:08x}'))
    return records

def targets(record, transform):
    sx,sy,left,top=transform
    y=np.zeros((GRID,GRID,6),np.float32)
    for box in sorted(record['boxes'],key=lambda b:(b[2]-b[0])*(b[3]-b[1]),reverse=True):
        x1,y1,x2,y2=box; cx=((x1+x2)/2*sx+left)/SIZE; cy=((y1+y2)/2*sy+top)/SIZE
        gx,gy=cx*GRID,cy*GRID; ix,iy=min(GRID-1,int(gx)),min(GRID-1,int(gy))
        bw,bh=(x2-x1)*sx/SIZE,(y2-y1)*sy/SIZE
        radius=max(1,min(3,int(min(bw,bh)*GRID/3)))
        for yy in range(max(0,iy-radius),min(GRID,iy+radius+1)):
            for xx in range(max(0,ix-radius),min(GRID,ix+radius+1)):
                y[yy,xx,0]=max(y[yy,xx,0],np.exp(-((yy-iy)**2+(xx-ix)**2)/(2*max(.5,radius/2)**2)))
        y[iy,ix]=[1,gx-ix,gy-iy,bw,bh,1]
    return y

def detection_loss(target,prediction):
    p=tf.clip_by_value(prediction[...,0],1e-5,1-1e-5); truth=target[...,0]
    positive=tf.cast(truth==1,tf.float32); negative=tf.cast(truth<1,tf.float32)
    count=tf.maximum(1.,tf.reduce_sum(positive))
    heat=-tf.reduce_sum(positive*tf.square(1-p)*tf.math.log(p)+negative*tf.pow(1-truth,4)*tf.square(p)*tf.math.log(1-p))/count
    difference=(prediction[...,1:5]-target[...,1:5])*tf.constant([1.,1.,4.,4.])
    absolute=tf.abs(difference); smooth=tf.where(absolute<1,.5*tf.square(absolute),absolute-.5)
    box=tf.reduce_sum(smooth*target[...,5:6])/count
    return heat+5*box

def make_backbone(architecture='center'):
    full=keras.applications.MobileNetV2(input_shape=(SIZE,SIZE,3),alpha=.5 if architecture=='fpn' else .35,include_top=False,weights='imagenet')
    if architecture=='fpn':
        early=keras.layers.AveragePooling2D(2)(full.get_layer('block_6_expand_relu').output)
        middle=full.get_layer('block_13_expand_relu').output
        deep=keras.layers.UpSampling2D(2,interpolation='bilinear')(full.get_layer('block_16_project').output)
        features=keras.layers.Concatenate()([early,middle,deep])
    else: features=full.get_layer('block_13_expand_relu').output
    backbone=keras.Model(full.input,features,name='ground_mobilenet_features')
    backbone.trainable=False
    assert backbone.output_shape[1:3]==(GRID,GRID)
    return backbone

def make_head(channels,architecture='center'):
    inputs=keras.Input((GRID,GRID,channels))
    if architecture=='fpn':
        x=keras.layers.Conv2D(96,1,activation='relu')(inputs)
        x=keras.layers.SeparableConv2D(96,3,padding='same',activation='relu')(x)
        x=keras.layers.SeparableConv2D(96,3,padding='same',activation='relu')(x)
    else:
        x=keras.layers.Conv2D(64,1,activation='relu')(inputs)
        x=keras.layers.DepthwiseConv2D(3,padding='same',activation='relu')(x)
        x=keras.layers.Conv2D(64,1,activation='relu')(x)
    x=keras.layers.Conv2D(5,1,bias_initializer=keras.initializers.Constant([-4.6,0,0,-2,-2]))(x)
    return keras.Model(inputs,keras.layers.Activation('sigmoid')(x),name='ground_center_head')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--dataset',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True); parser.add_argument('--epochs',type=int,default=35)
    parser.add_argument('--max-train',type=int,default=3000); parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--architecture',choices=['center','fpn'],default='center')
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    tf.config.threading.set_intra_op_parallelism_threads(args.threads); tf.config.threading.set_inter_op_parallelism_threads(2)
    keras.utils.set_random_seed(SEED); tf.config.experimental.enable_op_determinism()
    started=time.time(); archive=zipfile.ZipFile(args.dataset); records=read_records(archive)
    training=[r for r in records if r['split']=='train' and not r['ignored']]
    positives=[r for r in training if r['boxes']]; negatives=[r for r in training if not r['boxes']]
    rng=np.random.default_rng(SEED); rng.shuffle(positives); rng.shuffle(negatives)
    selected=positives[:args.max_train//2]+negatives[:args.max_train-min(len(positives),args.max_train//2)]
    selected_ids={r['id'] for r in selected}
    for record in records: record['used_for_training']=record['id'] in selected_ids
    (args.output/'manifest.json').write_text(json.dumps({'seed':SEED,'grouping':'country and source numeric id // 100',
        'source_sha256':hashlib.file_digest(args.dataset.open('rb'),'sha256').hexdigest(),'records':records},indent=2),encoding='utf8')
    print('Split counts:',{s:sum(r['split']==s for r in records) for s in ['train','validation','test']},flush=True)
    print('Training images:',len(selected),'pothole positives:',sum(bool(r['boxes']) for r in selected),flush=True)
    backbone=make_backbone(args.architecture); backbone.save_weights(args.output/'backbone.weights.h5')
    # Cache deterministic backbone features on disk. Validation never enters the optimizer.
    feature_records=selected+[r for r in records if r['split']=='validation' and not r['ignored']]
    features=np.lib.format.open_memmap(args.output/'features.npy',mode='w+',dtype='float16',shape=(len(feature_records),*backbone.output_shape[1:]))
    labels=np.zeros((len(feature_records),GRID,GRID,6),np.float32)
    for offset in range(0,len(feature_records),16):
        images=[]
        for index,record in enumerate(feature_records[offset:offset+16],offset):
            image=Image.open(io.BytesIO(archive.read(record['image'])))
            value,transform=letterbox(image); images.append(value); labels[index]=targets(record,transform)
        features[offset:offset+len(images)]=backbone(np.stack(images),training=False).numpy().astype('float16')
        if offset%256==0: print('Feature cache:',offset,'/',len(feature_records),flush=True)
    features.flush(); np.save(args.output/'targets.npy',labels)
    count=len(selected); head=make_head(backbone.output_shape[-1],args.architecture)
    if args.architecture=='fpn':
        from fine_tune import localization_loss
        loss=localization_loss
    else: loss=detection_loss
    head.compile(optimizer=keras.optimizers.Adam(1e-3),loss=loss)
    # tf.data batches reference memory-mapped feature slices, keeping RAM bounded.
    def dataset(start,end,shuffle):
        indices=np.arange(start,end)
        def generate():
            order=indices.copy()
            if shuffle: rng.shuffle(order)
            for index in order: yield features[index].astype('float32'), labels[index]
        result=tf.data.Dataset.from_generator(generate,output_signature=(tf.TensorSpec(backbone.output_shape[1:],tf.float32),tf.TensorSpec((GRID,GRID,6),tf.float32)))
        options=tf.data.Options(); options.threading.private_threadpool_size=2
        return result.apply(tf.data.experimental.assert_cardinality(end-start)).with_options(options).batch(32).prefetch(1)
    history=head.fit(dataset(0,count,True),validation_data=dataset(count,len(feature_records),False),epochs=args.epochs,
        callbacks=[keras.callbacks.ModelCheckpoint(str(args.output/'head.weights.h5'),monitor='val_loss',save_best_only=True,save_weights_only=True),
                   keras.callbacks.ReduceLROnPlateau(monitor='val_loss',factor=.5,patience=4,min_lr=1e-5),
                   keras.callbacks.CSVLogger(str(args.output/'history.csv'))],verbose=2)
    head.load_weights(args.output/'head.weights.h5')
    inputs=keras.Input((SIZE,SIZE,3),batch_size=1,name='rgb_minus_one_to_one')
    model=keras.Model(inputs,head(backbone(inputs,training=False)),name='visionassist_ground_baseline')
    model.save(args.output/'ground_baseline.keras')
    converter=tf.lite.TFLiteConverter.from_keras_model(model)
    converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS]
    content=converter.convert(); (args.output/'ground_baseline.tflite').write_bytes(content)
    report={'architecture':'MobileNetV2 alpha 0.5 frozen ImageNet multi-scale features + 20x20 GIoU center/box head' if args.architecture=='fpn' else 'MobileNetV2 alpha 0.35 frozen ImageNet features + 20x20 center/box head',
        'architecture_key':args.architecture,
        'classes':['pothole (RDD2022 D40)'],'input':[1,SIZE,SIZE,3],'input_normalization':'RGB / 127.5 - 1',
        'output':[1,GRID,GRID,5],'channels':['probability','cell_offset_x','cell_offset_y','normalized_width','normalized_height'],
        'epochs':args.epochs,'training_images':count,'validation_images':len(feature_records)-count,'seed':SEED,
        'model_sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),'elapsed_seconds':time.time()-started,
        'tensorflow':tf.__version__,'keras':keras.__version__,'limitations':['Experimental road-image baseline; no safety validation','No curb, stair or generic uneven-ground classes','Adjacent source IDs grouped; location independence not established']}
    (args.output/'training.json').write_text(json.dumps(report,indent=2),encoding='utf8'); print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__': main()
