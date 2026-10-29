package ro.visionassist.app.ui

import ro.visionassist.core.detection.DetectedObject
import ro.visionassist.core.detection.Direction
import kotlin.math.roundToInt

/** Labels translate model categories only; they never infer an unsupported hazard class. */
object DetectionLabels {
    private val names = mapOf(
        "person" to "persoană", "bicycle" to "bicicletă", "car" to "mașină", "motorcycle" to "motocicletă",
        "airplane" to "avion", "bus" to "autobuz", "train" to "tren", "truck" to "camion", "boat" to "barcă",
        "traffic light" to "semafor", "fire hydrant" to "hidrant", "stop sign" to "indicator STOP",
        "parking meter" to "parcometru", "bench" to "bancă", "bird" to "pasăre", "cat" to "pisică", "dog" to "câine",
        "horse" to "cal", "sheep" to "oaie", "cow" to "vacă", "elephant" to "elefant", "bear" to "urs",
        "zebra" to "zebră", "giraffe" to "girafă", "backpack" to "rucsac", "umbrella" to "umbrelă",
        "handbag" to "geantă", "tie" to "cravată", "suitcase" to "valiză", "frisbee" to "disc frisbee",
        "skis" to "schiuri", "snowboard" to "placă de snowboard", "sports ball" to "minge", "kite" to "zmeu",
        "baseball bat" to "bâtă de baseball", "baseball glove" to "mănușă de baseball",
        "skateboard" to "skateboard", "surfboard" to "placă de surf", "tennis racket" to "rachetă de tenis",
        "bottle" to "sticlă", "wine glass" to "pahar de vin", "cup" to "cană", "fork" to "furculiță",
        "knife" to "cuțit", "spoon" to "lingură", "bowl" to "bol", "banana" to "banană", "apple" to "măr",
        "sandwich" to "sandviș", "orange" to "portocală", "broccoli" to "broccoli", "carrot" to "morcov",
        "hot dog" to "hot dog", "pizza" to "pizza", "donut" to "gogoașă", "cake" to "tort", "chair" to "scaun",
        "couch" to "canapea", "potted plant" to "plantă în ghiveci", "bed" to "pat", "dining table" to "masă",
        "toilet" to "toaletă", "tv" to "televizor", "laptop" to "laptop", "mouse" to "mouse",
        "remote" to "telecomandă", "keyboard" to "tastatură", "cell phone" to "telefon",
        "microwave" to "cuptor cu microunde", "oven" to "cuptor", "toaster" to "prăjitor de pâine",
        "sink" to "chiuvetă", "refrigerator" to "frigider", "book" to "carte", "clock" to "ceas",
        "vase" to "vază", "scissors" to "foarfecă", "teddy bear" to "ursuleț de pluș",
        "hair drier" to "uscător de păr", "toothbrush" to "periuță de dinți"
    )
    fun label(category: String): String = names[category] ?: category
    fun description(obj: DetectedObject): String {
        val direction = when (obj.bounds.direction) {
            Direction.Left -> "stânga"
            Direction.Center -> "centru"
            Direction.Right -> "dreapta"
        }
        return "${label(obj.label)} · ${(obj.confidence * 100).roundToInt()}% · $direction"
    }
}
