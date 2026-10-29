"""Compare real Python/Android task outputs on identical, hashed fixture pixels."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

CLASSES={'stairs','curb','step'}


def validate(detections,width,height):
    for value in detections:
        if value['class'] not in CLASSES or not math.isfinite(value['score']) or not 0<=value['score']<=1:
            raise ValueError('Invalid class/score in recorded output')
        box=value['box']
        if len(box)!=4 or not all(map(math.isfinite,box)) or not (
                0<=box[0]<box[2]<=width and 0<=box[1]<box[3]<=height):
            raise ValueError('Invalid clipped box in recorded output')


def compare(expected,actual,threshold,score_tolerance=.001,pixel_tolerance=2.):
    """Maximize coverage of all outputs outside the explicit threshold ambiguity band.

    Optional borderline outputs may match a required output. Dummy rows/columns allow
    unmatched outputs. The required-endpoint bonus dominates every cardinality gain.
    """
    if (not all(map(math.isfinite,(threshold,score_tolerance,pixel_tolerance))) or
            not 0<=threshold<=1 or not 0<score_tolerance<1 or not pixel_tolerance>0):
        raise ValueError('Invalid comparison threshold/tolerance')
    e=[p for p in expected if p['score']>=threshold-score_tolerance-1e-8]
    a=[p for p in actual if p['score']>=threshold-score_tolerance-1e-8]
    er=[p['score']>threshold+score_tolerance+1e-8 for p in e]
    ar=[p['score']>threshold+score_tolerance+1e-8 for p in a]
    size=len(e)+len(a)
    pairs=[]
    if size:
        weights=np.zeros((size,size),dtype=np.float64)
        weights[:len(e),:len(a)]=-1
        compatible=set()
        for i,left in enumerate(e):
            for j,right in enumerate(a):
                if (left['class']==right['class'] and
                        abs(left['score']-right['score'])<=score_tolerance+1e-8 and
                        max(abs(x-y) for x,y in zip(left['box'],right['box']))<=pixel_tolerance+1e-8):
                    compatible.add((i,j))
                    weights[i,j]=1+(size+1)*(int(er[i])+int(ar[j]))
        rows,columns=linear_sum_assignment(weights,maximize=True)
        pairs=[(int(i),int(j)) for i,j in zip(rows,columns) if (int(i),int(j)) in compatible]
    matched_e={i for i,j in pairs}; matched_a={j for i,j in pairs}
    missing_e=[dict(index=i,detection=p) for i,p in enumerate(e) if er[i] and i not in matched_e]
    missing_a=[dict(index=j,detection=p) for j,p in enumerate(a) if ar[j] and j not in matched_a]
    return dict(passed=not missing_e and not missing_a,matched_pairs=len(pairs),
                required_python=sum(er),required_android=sum(ar),
                borderline_python=len(e)-sum(er),borderline_android=len(a)-sum(ar),
                unmatched_python=missing_e,unmatched_android=missing_a,
                max_score_error=max((abs(e[i]['score']-a[j]['score']) for i,j in pairs),default=None),
                max_coordinate_error_px=max((max(abs(x-y) for x,y in zip(e[i]['box'],a[j]['box'])) for i,j in pairs),default=None))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--android-results',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--python-results',type=Path)
    parser.add_argument('--score-tolerance',type=float,default=.001)
    parser.add_argument('--pixel-tolerance',type=float,default=2.)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new comparison output file')
    raw=(args.fixtures/'fixture.json').read_bytes()
    fixture=json.loads(raw)
    result_raw=args.android_results.read_bytes()
    android=json.loads(result_raw.decode('utf-16' if result_raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'))
    if (android['fixture_sha256']!=hashlib.sha256(raw).hexdigest() or
            android['model_sha256']!=fixture['model_sha256'] or not android['test_only'] or not fixture['test_only']):
        raise ValueError('Recorded Android model/fixture identity differs')
    if hashlib.sha256((args.fixtures/'model.tflite').read_bytes()).hexdigest()!=fixture['model_sha256']:
        raise ValueError('Local fixture model changed')
    expected={r['file']:r for r in fixture['records']}; actual={r['file']:r for r in android['records']}
    if (len(expected)!=len(fixture['records']) or len(actual)!=len(android['records']) or set(expected)!=set(actual)):
        raise ValueError('Missing or duplicate fixture frames')
    reference=None
    if args.python_results:
        reference=json.loads(args.python_results.read_text(encoding='utf-8-sig'))
        if (reference['model_sha256']!=fixture['model_sha256'] or
                reference['fixture_sha256']!=android['fixture_sha256'] or not reference['test_only']):
            raise ValueError('Alternate Python reference identity differs')
        alternate={r['file']:r for r in reference['records']}
        if len(alternate)!=len(reference['records']) or set(alternate)!=set(expected):
            raise ValueError('Alternate reference image inventory differs')
    frames=[]
    for name,left in expected.items():
        if Path(name).name!=name or '\\' in name: raise ValueError('Invalid fixture image path')
        right=actual[name]
        if (right['png_sha256']!=left['png_sha256'] or
                right['rgb_sha256']!=left['rgb_sha256'] or
                hashlib.sha256((args.fixtures/name).read_bytes()).hexdigest()!=left['png_sha256'] or
                (left['width'],left['height'])!=(right['width'],right['height'])):
            raise ValueError('Recorded fixture pixels/dimensions differ')
        python_predictions=left['python_predictions']
        if reference:
            other=alternate[name]
            if (other['png_sha256']!=left['png_sha256'] or other['rgb_sha256']!=left['rgb_sha256'] or
                    (other['width'],other['height'])!=(left['width'],left['height'])):
                raise ValueError('Alternate Python reference pixels differ')
            python_predictions=other['predictions']
        validate(python_predictions,left['width'],left['height'])
        validate(right['predictions'],right['width'],right['height'])
        frames.append(dict(file=name,python_count=len(python_predictions),android_count=len(right['predictions']),
                           thresholds={str(t):compare(python_predictions,right['predictions'],t,
                                                     args.score_tolerance,args.pixel_tolerance) for t in (.3,.65)}))
    passed=all(v['passed'] for frame in frames for v in frame['thresholds'].values())
    report=dict(passed=passed,model_sha256=fixture['model_sha256'],fixture_sha256=android['fixture_sha256'],
                python_runtime=reference['runtime'] if reference else f'MediaPipe Python {fixture["mediapipe_version"]}',
                python_results_sha256=hashlib.sha256(args.python_results.read_bytes()).hexdigest() if reference else None,
                device=android['device'],runtime=android['runtime'],smoke_model=fixture['smoke_model'],
                score_tolerance=args.score_tolerance,pixel_tolerance=args.pixel_tolerance,frames=frames,
                accuracy_approved=False,warning_eligible=False,
                scope='Class/score/clipped-box output agreement at 0.3 and 0.65, with an explicit score-tolerance ambiguity band. Not raw tensor equality or accuracy evidence.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(dict(passed=passed,frames=len(frames),model_sha256=fixture['model_sha256'],output=str(args.output)),indent=2))
    return 0 if passed else 2


if __name__=='__main__': raise SystemExit(main())
