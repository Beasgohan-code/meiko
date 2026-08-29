import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class Composer extends StatefulWidget {
  final void Function(String text) onSend;
  final VoidCallback onAttach;
  final bool isStreaming;
  final VoidCallback onStop;

  const Composer({
    super.key,
    required this.onSend,
    required this.onAttach,
    required this.isStreaming,
    required this.onStop,
  });

  @override
  State<Composer> createState() => _ComposerState();
}

class _ComposerState extends State<Composer> {
  final _controller = TextEditingController();

  void _handleSend() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    widget.onSend(text);
    _controller.clear();
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 8, 14, 12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
          decoration: BoxDecoration(
            color: MeikoColors.panel,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: MeikoColors.border),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              IconButton(
                icon: const Icon(Icons.attach_file, size: 20, color: MeikoColors.text1),
                onPressed: widget.onAttach,
              ),
              Expanded(
                child: TextField(
                  controller: _controller,
                  minLines: 1,
                  maxLines: 6,
                  style: const TextStyle(color: MeikoColors.text0, fontSize: 14.5),
                  decoration: const InputDecoration(
                    hintText: 'Message Meiko…',
                    hintStyle: TextStyle(color: MeikoColors.text2),
                    border: InputBorder.none,
                    filled: false,
                    contentPadding: EdgeInsets.symmetric(vertical: 10),
                  ),
                  onChanged: (_) => setState(() {}),
                  onSubmitted: (_) => _handleSend(),
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(left: 4),
                child: widget.isStreaming
                    ? IconButton(
                        icon: const Icon(Icons.stop_circle, color: MeikoColors.text1),
                        onPressed: widget.onStop,
                      )
                    : Container(
                        decoration: BoxDecoration(gradient: meikoGradient(), shape: BoxShape.circle),
                        child: IconButton(
                          icon: const Icon(Icons.arrow_upward, color: Colors.white, size: 20),
                          onPressed: _controller.text.trim().isEmpty ? null : _handleSend,
                        ),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
