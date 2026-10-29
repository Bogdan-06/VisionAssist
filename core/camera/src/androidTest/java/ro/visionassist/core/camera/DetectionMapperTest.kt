package ro.visionassist.core.camera

import android.graphics.Matrix
import android.graphics.Rect
import android.util.Size
import androidx.camera.core.ImageInfo
import androidx.camera.core.ImageProxy
import androidx.camera.view.TransformExperimental
import androidx.camera.view.transform.ImageProxyTransformFactory
import androidx.camera.view.transform.OutputTransform
import org.junit.Assert.*
import org.junit.Test
import ro.visionassist.core.detection.ImageDetection
import ro.visionassist.core.detection.PixelBox
import ro.visionassist.core.detection.ViewBox
import java.lang.reflect.Proxy

@androidx.annotation.OptIn(TransformExperimental::class)
class DetectionMapperTest {
    private fun image(rotation: Int, crop: Rect): ImageProxy {
        val info = Proxy.newProxyInstance(ImageInfo::class.java.classLoader, arrayOf(ImageInfo::class.java)) { _, method, _ ->
            when (method.name) { "getRotationDegrees" -> rotation; else -> error("Unexpected ${method.name}") }
        } as ImageInfo
        return Proxy.newProxyInstance(ImageProxy::class.java.classLoader, arrayOf(ImageProxy::class.java)) { _, method, _ ->
            when (method.name) {
                "getWidth" -> 640
                "getHeight" -> 480
                "getCropRect" -> crop
                "getImageInfo" -> info
                else -> error("Unexpected ${method.name}")
            }
        } as ImageProxy
    }

    @Test fun rotatedFullBufferBoxesMapToSharedCroppedViewportAtAllFourRotations() {
        // One physical sensor box (120,120)-(240,240), expressed in each upright bitmap.
        val rotations = listOf(0, 90, 180, 270)
        val boxes = listOf(PixelBox(120f,120f,240f,240f), PixelBox(240f,120f,360f,240f),
            PixelBox(400f,240f,520f,360f), PixelBox(120f,400f,240f,520f))
        val expected = listOf(ViewBox(1f/12,0.25f,1f/3,0.5f), ViewBox(0.5f,1f/12,0.75f,1f/3),
            ViewBox(2f/3,0.5f,11f/12,0.75f), ViewBox(0.25f,2f/3,0.5f,11f/12))
        val matrices = listOf(
            floatArrayOf(200f,0f,200f,0f,200f,200f,0f,0f,1f),
            floatArrayOf(0f,-200f,200f,200f,0f,200f,0f,0f,1f),
            floatArrayOf(-200f,0f,200f,0f,-200f,200f,0f,0f,1f),
            floatArrayOf(0f,200f,200f,-200f,0f,200f,0f,0f,1f)
        )
        rotations.forEachIndexed { index, rotation ->
            val source = ImageProxyTransformFactory().apply {
                isUsingCropRect = false
                isUsingRotationDegrees = true
            }.getOutputTransform(image(rotation, Rect(80,0,560,480)))
            val target = OutputTransform(Matrix().apply { setValues(matrices[index]) }, Size(480,480))
            val result = mapDetections(listOf(ImageDetection("person",0.9f,boxes[index])), source, target,400,400).single()
            assertBox("rotation $rotation", expected[index], result.bounds)
        }
    }

    @Test fun wideCenterCropRescalesAndDropsObjectsOutsidePreview() {
        val source = ImageProxyTransformFactory().getOutputTransform(image(0, Rect(0,80,640,400)))
        val target = OutputTransform(Matrix().apply {
            setValues(floatArrayOf(500f,0f,500f,0f,250f,250f,0f,0f,1f))
        }, Size(640,320))
        val result = mapDetections(listOf(
            ImageDetection("car",0.9f,PixelBox(80f,120f,240f,240f)),
            ImageDetection("person",0.9f,PixelBox(0f,0f,20f,40f))
        ), source, target,1000,500)
        assertEquals(1,result.size)
        assertBox("wide preview",ViewBox(0.125f,0.125f,0.375f,0.5f),result.single().bounds)
    }

    private fun assertBox(message: String, expected: ViewBox, actual: ViewBox) {
        assertEquals(message,expected.left,actual.left,0.0001f)
        assertEquals(message,expected.top,actual.top,0.0001f)
        assertEquals(message,expected.right,actual.right,0.0001f)
        assertEquals(message,expected.bottom,actual.bottom,0.0001f)
    }
}
