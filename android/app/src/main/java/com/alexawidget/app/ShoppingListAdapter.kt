package com.alexawidget.app

import android.content.Context
import android.graphics.Paint
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.ImageButton
import android.widget.TextView

/** Cada linha: toque no texto alterna comprado/não comprado; lápis edita; lixeira remove. */
class ShoppingListAdapter(
    private val context: Context,
    private val onToggle: (ApiClient.ShoppingItem) -> Unit,
    private val onEdit: (ApiClient.ShoppingItem) -> Unit,
    private val onDelete: (ApiClient.ShoppingItem) -> Unit,
) : BaseAdapter() {

    private var items: List<ApiClient.ShoppingItem> = emptyList()

    fun submitList(newItems: List<ApiClient.ShoppingItem>) {
        items = newItems
        notifyDataSetChanged()
    }

    override fun getCount(): Int = items.size

    override fun getItem(position: Int): ApiClient.ShoppingItem = items[position]

    override fun getItemId(position: Int): Long = items[position].id.hashCode().toLong()

    override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
        val view = convertView
            ?: LayoutInflater.from(context).inflate(R.layout.list_row_item, parent, false)
        val item = items[position]

        val textView = view.findViewById<TextView>(R.id.row_item_text)
        textView.text = item.text
        textView.paintFlags = if (item.completed) {
            textView.paintFlags or Paint.STRIKE_THRU_TEXT_FLAG
        } else {
            textView.paintFlags and Paint.STRIKE_THRU_TEXT_FLAG.inv()
        }
        textView.alpha = if (item.completed) 0.6f else 1f
        textView.setOnClickListener { onToggle(item) }

        view.findViewById<ImageButton>(R.id.row_item_edit).setOnClickListener { onEdit(item) }
        view.findViewById<ImageButton>(R.id.row_item_delete).setOnClickListener { onDelete(item) }

        return view
    }
}
