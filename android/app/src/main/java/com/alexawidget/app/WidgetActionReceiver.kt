package com.alexawidget.app

import android.appwidget.AppWidgetManager
import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * Recebe os toques nos itens da lista dentro do widget (marcar como comprado,
 * remover) e no botão de atualizar. As chamadas de rede aqui rodam em uma
 * thread separada via goAsync(), já que BroadcastReceiver.onReceive() roda na
 * thread principal e não pode bloquear.
 */
class WidgetActionReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.getStringExtra(EXTRA_ACTION)
        val appWidgetId = intent.getIntExtra(
            AppWidgetManager.EXTRA_APPWIDGET_ID,
            AppWidgetManager.INVALID_APPWIDGET_ID,
        )

        if (action == ACTION_REFRESH || action == null) {
            // Refresh manual (botão "Atualizar"): itens já comprados devem
            // sumir do widget na hora, não só depois dos 10 min de atraso.
            CompletedItemTracker(context).markForceClearOnNextUpdate()
            refreshWidget(context, appWidgetId)
            return
        }

        val itemId = intent.getStringExtra(EXTRA_ITEM_ID)
        if (itemId.isNullOrEmpty()) {
            refreshWidget(context, appWidgetId)
            return
        }

        val pendingResult = goAsync()
        Thread {
            try {
                if (action == ACTION_TOGGLE_COMPLETE) {
                    val targetCompleted = intent.getBooleanExtra(EXTRA_TARGET_COMPLETED, true)
                    ApiClient(context).setItemCompletedBlocking(itemId, targetCompleted)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Falha ao executar ação '$action' no item $itemId", e)
            } finally {
                refreshWidget(context, appWidgetId)
                pendingResult.finish()
            }
        }.start()
    }

    private fun refreshWidget(context: Context, appWidgetId: Int) {
        val manager = AppWidgetManager.getInstance(context)
        if (appWidgetId != AppWidgetManager.INVALID_APPWIDGET_ID) {
            manager.notifyAppWidgetViewDataChanged(appWidgetId, R.id.widget_list)
        } else {
            val ids = manager.getAppWidgetIds(ComponentName(context, ShoppingListWidgetProvider::class.java))
            manager.notifyAppWidgetViewDataChanged(ids, R.id.widget_list)
        }
    }

    companion object {
        private const val TAG = "WidgetActionReceiver"
        const val EXTRA_ACTION = "com.alexawidget.app.EXTRA_ACTION"
        const val EXTRA_ITEM_ID = "com.alexawidget.app.EXTRA_ITEM_ID"
        const val EXTRA_TARGET_COMPLETED = "com.alexawidget.app.EXTRA_TARGET_COMPLETED"
        const val ACTION_TOGGLE_COMPLETE = "toggle_complete"
        const val ACTION_REFRESH = "refresh"
    }
}
