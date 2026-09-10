package com.alexawidget.app

import android.content.Context
import android.content.Intent
import android.graphics.Paint
import android.util.Log
import android.widget.RemoteViews
import android.widget.RemoteViewsService

/**
 * Busca a lista de compras e monta cada linha do widget.
 *
 * onDataSetChanged() é o único lugar onde é permitido (e esperado) bloquear
 * com I/O de rede: o sistema já executa isso em uma thread de trabalho
 * separada, então uma chamada HTTP síncrona aqui é o padrão documentado.
 */
class ShoppingListRemoteViewsFactory(
    private val context: Context,
    @Suppress("UNUSED_PARAMETER") appWidgetId: Int,
) : RemoteViewsService.RemoteViewsFactory {

    private var items: List<ApiClient.ShoppingItem> = emptyList()
    private val api = ApiClient(context)
    private val completedTracker = CompletedItemTracker(context)

    override fun onCreate() {}

    override fun onDataSetChanged() {
        items = try {
            val fetched = api.listItemsBlocking()
            val forceClear = completedTracker.consumeForceClear()
            val completedIds = fetched.filter { it.completed }.map { it.id }.toSet()
            val hiddenIds = completedTracker.updateAndGetHidden(completedIds, forceClear)
            fetched.filter { it.id !in hiddenIds }.sortedBy { it.completed }
        } catch (e: Exception) {
            Log.e(TAG, "Falha ao carregar a lista de compras", e)
            emptyList()
        }
    }

    override fun onDestroy() {
        items = emptyList()
    }

    override fun getCount(): Int = items.size

    override fun getViewAt(position: Int): RemoteViews {
        val item = items[position]
        val views = RemoteViews(context.packageName, R.layout.widget_item)

        views.setTextViewText(R.id.item_text, item.text)
        views.setImageViewResource(
            R.id.item_check,
            if (item.completed) R.drawable.ic_checkbox_checked else R.drawable.ic_checkbox_unchecked,
        )
        val paintFlags = if (item.completed) {
            Paint.STRIKE_THRU_TEXT_FLAG or Paint.ANTI_ALIAS_FLAG
        } else {
            Paint.ANTI_ALIAS_FLAG
        }
        views.setInt(R.id.item_text, "setPaintFlags", paintFlags)

        // O alvo do toque é a linha inteira (não só o ícone), pra um toque
        // mais fácil de acertar; alterna o estado (marca se estava
        // desmarcado, desmarca se estava marcado).
        val toggleFillInIntent = Intent().apply {
            putExtra(WidgetActionReceiver.EXTRA_ACTION, WidgetActionReceiver.ACTION_TOGGLE_COMPLETE)
            putExtra(WidgetActionReceiver.EXTRA_ITEM_ID, item.id)
            putExtra(WidgetActionReceiver.EXTRA_TARGET_COMPLETED, !item.completed)
        }
        views.setOnClickFillInIntent(R.id.item_row, toggleFillInIntent)

        return views
    }

    override fun getLoadingView(): RemoteViews? = null

    override fun getViewTypeCount(): Int = 1

    override fun getItemId(position: Int): Long =
        items.getOrNull(position)?.id?.hashCode()?.toLong() ?: position.toLong()

    override fun hasStableIds(): Boolean = true

    companion object {
        private const val TAG = "ShoppingListWidget"
    }
}
