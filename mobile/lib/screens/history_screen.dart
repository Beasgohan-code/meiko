import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../providers/meiko_provider.dart';
import '../theme/app_theme.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

String _formatUpdatedAt(double epochSeconds) {
  if (epochSeconds <= 0) return '';
  final dt = DateTime.fromMillisecondsSinceEpoch((epochSeconds * 1000).round(), isUtc: true).toLocal();
  final now = DateTime.now();
  final diff = now.difference(dt);
  if (diff.inMinutes < 1) return 'just now';
  if (diff.inHours < 1) return '${diff.inMinutes}m ago';
  if (diff.inDays < 1) return '${diff.inHours}h ago';
  if (diff.inDays < 7) return '${diff.inDays}d ago';
  return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<ConversationSummary> _items = [];
  bool _loading = true;
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh({String? query}) async {
    setState(() => _loading = true);
    final meiko = context.read<MeikoProvider>();
    final items = await meiko.loadHistory(query: query);
    if (!mounted) return;
    setState(() {
      _items = items;
      _loading = false;
    });
  }

  Future<void> _rename(ConversationSummary c) async {
    final controller = TextEditingController(text: c.title);
    final newTitle = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: MeikoColors.panel,
        title: const Text('Rename conversation'),
        content: TextField(controller: controller, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('Save')),
        ],
      ),
    );
    if (newTitle == null || newTitle.isEmpty) return;
    final meiko = context.read<MeikoProvider>();
    await meiko.renameConversation(c.id, newTitle);
    _refresh(query: _searchController.text);
  }

  Future<void> _delete(ConversationSummary c) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: MeikoColors.panel,
        title: const Text('Delete conversation?'),
        content: Text('"${c.title}" will be permanently deleted.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete', style: TextStyle(color: MeikoColors.danger))),
        ],
      ),
    );
    if (confirmed != true) return;
    final meiko = context.read<MeikoProvider>();
    await meiko.deleteConversation(c.id);
    _refresh(query: _searchController.text);
  }

  Future<void> _togglePin(ConversationSummary c) async {
    final meiko = context.read<MeikoProvider>();
    await meiko.pinConversation(c.id, !c.pinned);
    _refresh(query: _searchController.text);
  }

  Future<void> _open(ConversationSummary c) async {
    final meiko = context.read<MeikoProvider>();
    await meiko.openConversation(c.id);
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('History'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search conversations…',
                prefixIcon: const Icon(Icons.search, size: 18),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.close, size: 16),
                        onPressed: () {
                          _searchController.clear();
                          _refresh();
                        },
                      )
                    : null,
              ),
              onSubmitted: (q) => _refresh(query: q),
              onChanged: (q) {
                if (q.isEmpty) _refresh();
              },
            ),
          ),
          if (_loading) const Expanded(child: Center(child: CircularProgressIndicator(color: MeikoColors.violet))),
          if (!_loading && _items.isEmpty)
            const Expanded(
              child: Center(
                child: Text('No conversations yet.', style: TextStyle(color: MeikoColors.text2)),
              ),
            ),
          if (!_loading && _items.isNotEmpty)
            Expanded(
              child: ListView.builder(
                itemCount: _items.length,
                itemBuilder: (context, i) {
                  final c = _items[i];
                  return ListTile(
                    leading: Icon(c.pinned ? Icons.push_pin : Icons.chat_bubble_outline,
                        size: 18, color: c.pinned ? MeikoColors.violetSoft : MeikoColors.text2),
                    title: Text(c.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5)),
                    subtitle: Text(_formatUpdatedAt(c.updatedAt), style: const TextStyle(fontSize: 10.5, color: MeikoColors.text2)),
                    onTap: () => _open(c),
                    trailing: PopupMenuButton<String>(
                      icon: const Icon(Icons.more_vert, size: 18, color: MeikoColors.text2),
                      color: MeikoColors.panel,
                      onSelected: (v) {
                        if (v == 'rename') _rename(c);
                        if (v == 'delete') _delete(c);
                        if (v == 'pin') _togglePin(c);
                      },
                      itemBuilder: (ctx) => [
                        PopupMenuItem(value: 'pin', child: Text(c.pinned ? 'Unpin' : 'Pin')),
                        const PopupMenuItem(value: 'rename', child: Text('Rename')),
                        const PopupMenuItem(value: 'delete', child: Text('Delete')),
                      ],
                    ),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}
