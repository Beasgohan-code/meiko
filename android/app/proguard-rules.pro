# Meiko Android — ProGuard/R8 rules
-keepattributes *Annotation*
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keepclasseswithmembers class kotlinx.serialization.json.** { kotlinx.serialization.KSerializer serializer(...); }
-keep,includedescriptorclasses class ai.meiko.app.**$$serializer { *; }
-keepclassmembers class ai.meiko.app.** { *** Companion; }
-keepclasseswithmembers class ai.meiko.app.** { kotlinx.serialization.KSerializer serializer(...); }

# Ktor CIO engine references slf4j optionally at runtime; we don't ship a binding.
-dontwarn org.slf4j.**
-dontwarn io.netty.**
-dontwarn reactor.blockhound.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
