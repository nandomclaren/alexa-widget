package com.alexawidget.app

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONObject

/**
 * Controla há quanto tempo cada item está marcado como comprado, pra decidir
 * quando ele deve sumir do widget: por padrão só some [HIDE_AFTER_MILLIS]
 * depois de marcado, exceto quando o usuário toca em "Atualizar" no widget —
 * aí os já comprados somem na hora (ver [consumeForceClear]).
 */
class CompletedItemTracker(context: Context) {

    private val prefs: SharedPreferences =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Atualiza os carimbos de data/hora e devolve os ids que devem ficar ocultos agora. */
    fun updateAndGetHidden(completedIds: Set<String>, forceClearAll: Boolean): Set<String> {
        val now = System.currentTimeMillis()
        val stored = readTimestamps()
        val next = mutableMapOf<String, Long>()
        val hidden = mutableSetOf<String>()

        for (id in completedIds) {
            val completedAt = stored[id] ?: now
            next[id] = completedAt
            if (forceClearAll || now - completedAt >= HIDE_AFTER_MILLIS) {
                hidden.add(id)
            }
        }
        writeTimestamps(next)
        return hidden
    }

    fun markForceClearOnNextUpdate() {
        prefs.edit().putBoolean(KEY_FORCE_CLEAR, true).apply()
    }

    /** Lê e já reseta a flag (efeito de "uma vez só" no próximo onDataSetChanged). */
    fun consumeForceClear(): Boolean {
        val value = prefs.getBoolean(KEY_FORCE_CLEAR, false)
        if (value) prefs.edit().putBoolean(KEY_FORCE_CLEAR, false).apply()
        return value
    }

    private fun readTimestamps(): Map<String, Long> {
        val raw = prefs.getString(KEY_TIMESTAMPS, null) ?: return emptyMap()
        return try {
            val json = JSONObject(raw)
            json.keys().asSequence().associateWith { json.getLong(it) }
        } catch (e: Exception) {
            emptyMap()
        }
    }

    private fun writeTimestamps(map: Map<String, Long>) {
        val json = JSONObject()
        for ((id, time) in map) json.put(id, time)
        prefs.edit().putString(KEY_TIMESTAMPS, json.toString()).apply()
    }

    companion object {
        private const val PREFS_NAME = "alexa_widget_completed_tracker"
        private const val KEY_TIMESTAMPS = "timestamps"
        private const val KEY_FORCE_CLEAR = "force_clear"
        private const val HIDE_AFTER_MILLIS = 10 * 60 * 1000L
    }
}
