# The precompiled WebRTC AAR has JNI lookups but no consumer ProGuard rules.
# Preserve its Java/native ABI in optimized builds.
-keep class org.webrtc.** { *; }
# Do not retain the unused Chromium JniZero loader: this standalone AAR does not
# ship its generated JniZeroJni companion. WebRTC uses its own native loader.
