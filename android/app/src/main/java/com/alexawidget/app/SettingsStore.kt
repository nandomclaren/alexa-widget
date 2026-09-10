package com.alexawidget.app

import android.content.Context
import android.content.SharedPreferences

/** Guarda a URL do servidor e o Bearer token localmente no aparelho. */
class SettingsStore(context: Context) {

    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER_URL, DEFAULT_SERVER_URL) ?: DEFAULT_SERVER_URL
        set(value) = prefs.edit().putString(KEY_SERVER_URL, value).apply()

    var token: String
        get() = prefs.getString(KEY_TOKEN, "") ?: ""
        set(value) = prefs.edit().putString(KEY_TOKEN, value).apply()

    companion object {
        private const val PREFS_NAME = "alexa_widget_settings"
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_TOKEN = "token"
        private const val DEFAULT_SERVER_URL = "https://alexa-widget-production.up.railway.app"
    }
}
