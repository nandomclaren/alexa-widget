package com.alexawidget.app

import android.app.Application
import com.google.android.material.color.DynamicColors

/** Ativa Material You (cores do sistema) nas telas do app, quando disponível (Android 12+). */
class AlexaWidgetApp : Application() {
    override fun onCreate() {
        super.onCreate()
        DynamicColors.applyToActivitiesIfAvailable(this)
    }
}
