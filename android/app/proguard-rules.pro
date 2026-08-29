# Meiko Android — ProGuard/R8 rules
-keepattributes *Annotation*
-keepclassmembers class kotlinx.serialization.json.** { *** Companion; }
-keepclasseswithmembers class kotlinx.serialization.json.** { kotlinx.serialization.KSerializer serializer(...); }
-keep,includedescriptorclasses class ai.meiko.app.**$$serializer { *; }
-keepclassmembers class ai.meiko.app.** { *** Companion; }
-keepclasseswithmembers class ai.meiko.app.** { kotlinx.serialization.KSerializer serializer(...); }
