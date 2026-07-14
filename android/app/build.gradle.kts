plugins {
    id("com.android.application")
}

val releaseKeystorePath = System.getenv("CHECKIN_KEYSTORE_PATH")
val releaseKeystorePassword = System.getenv("CHECKIN_KEYSTORE_PASSWORD")
val releaseKeyAlias = System.getenv("CHECKIN_KEY_ALIAS")
val releaseKeyPassword = System.getenv("CHECKIN_KEY_PASSWORD")

android {
    namespace = "cn.edu.suse.checkin"
    compileSdk = 37

    defaultConfig {
        applicationId = "cn.edu.suse.checkin"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "1.0.0"
    }

    signingConfigs {
        if (!releaseKeystorePath.isNullOrBlank()
            && !releaseKeystorePassword.isNullOrBlank()
            && !releaseKeyAlias.isNullOrBlank()
            && !releaseKeyPassword.isNullOrBlank()
        ) {
            create("release") {
                storeFile = file(releaseKeystorePath)
                storePassword = releaseKeystorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
                enableV1Signing = true
                enableV2Signing = true
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions {
        unitTests.isIncludeAndroidResources = false
    }

    lint {
        // AGP 9.2.0 officially pins Gradle 9.4.1; do not suggest an
        // unvalidated wrapper upgrade independently of the Android plugin.
        disable += "AndroidGradlePluginVersion"
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
