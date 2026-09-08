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

    override fun onCreate() {}

    override fun onDataSetChanged() {
        items = try {
            api.listItemsBlocking().sortedBy { it.completed }
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

        val checkFillInIntent = Intent().apply {
            putExtra(WidgetActionReceiver.EXTRA_ACTION, WidgetActionReceiver.ACTION_COMPLETE)
            putExtra(WidgetActionReceiver.EXTRA_ITEM_ID, item.id)
        }
        views.setOnClickFillInIntent(R.id.item_check, checkFillInIntent)

        val deleteFillInIntent = Intent().apply {
            putExtra(WidgetActionReceiver.EXTRA_ACTION, WidgetActionReceiver.ACTION_DELETE)
            putExtra(WidgetActionReceiver.EXTRA_ITEM_ID, item.id)
        }
        views.setOnClickFillInIntent(R.id.item_delete, deleteFillInIntent)

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
