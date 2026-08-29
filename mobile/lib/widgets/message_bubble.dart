import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import '../models/models.dart';
import '../theme/app_theme.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  const MessageBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == ChatRole.user;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) _Avatar(isUser: false),
          if (!isUser) const SizedBox(width: 10),
          Flexible(
            child: Column(
              crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                if (!isUser && message.tools.isNotEmpty) _ToolTrace(tools: message.tools),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.74),
                  decoration: BoxDecoration(
                    gradient: isUser
                        ? LinearGradient(
                            colors: [MeikoColors.violet.withOpacity(0.35), MeikoColors.cyan.withOpacity(0.2)],
                          )
                        : null,
                    color: isUser ? null : MeikoColors.panel,
                    border: Border.all(
                      color: isUser ? MeikoColors.violet.withOpacity(0.4) : MeikoColors.border,
                    ),
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(16),
                      topRight: const Radius.circular(16),
                      bottomLeft: Radius.circular(isUser ? 16 : 4),
                      bottomRight: Radius.circular(isUser ? 4 : 16),
                    ),
                  ),
                  child: message.streaming && message.content.isEmpty
                      ? const _ThinkingDots()
                      : MarkdownBody(
                          data: message.content.isEmpty ? '…' : message.content,
                          selectable: true,
                          styleSheet: MarkdownStyleSheet(
                            p: const TextStyle(color: MeikoColors.text0, fontSize: 14.5, height: 1.5),
                            code: TextStyle(
                              backgroundColor: MeikoColors.violet.withOpacity(0.15),
                              fontFamily: 'monospace',
                              fontSize: 13,
                            ),
                            codeblockDecoration: BoxDecoration(
                              color: const Color(0xFF0A0A18),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: MeikoColors.border),
                            ),
                            a: const TextStyle(color: MeikoColors.cyan),
                          ),
                        ),
                ),
                if (message.error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('⚠ ${message.error}', style: const TextStyle(color: MeikoColors.danger, fontSize: 12.5)),
                  ),
              ],
            ),
          ),
          if (isUser) const SizedBox(width: 10),
          if (isUser) _Avatar(isUser: true),
        ],
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  final bool isUser;
  const _Avatar({required this.isUser});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 30,
      height: 30,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: isUser ? null : meikoGradient(),
        color: isUser ? Colors.white.withOpacity(0.08) : null,
        border: isUser ? Border.all(color: MeikoColors.border) : null,
      ),
      alignment: Alignment.center,
      child: Text(
        isUser ? 'U' : 'M',
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.bold,
          color: isUser ? MeikoColors.text1 : Colors.white,
        ),
      ),
    );
  }
}

class _ToolTrace extends StatelessWidget {
  final List<ToolTrace> tools;
  const _ToolTrace({required this.tools});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: tools
            .map((t) => Container(
                  margin: const EdgeInsets.only(bottom: 5),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: MeikoColors.cyan.withOpacity(0.08),
                    border: Border.all(color: MeikoColors.cyan.withOpacity(0.2)),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      t.status == ToolStatus.calling
                          ? const SizedBox(
                              width: 11,
                              height: 11,
                              child: CircularProgressIndicator(strokeWidth: 2, color: MeikoColors.violetSoft),
                            )
                          : const Icon(Icons.check_circle, size: 13, color: MeikoColors.success),
                      const SizedBox(width: 6),
                      Icon(Icons.build, size: 12, color: MeikoColors.text1),
                      const SizedBox(width: 6),
                      Text(t.name, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: MeikoColors.text0)),
                      if (t.result != null) ...[
                        const SizedBox(width: 6),
                        Flexible(
                          child: Text(
                            t.result!.length > 60 ? '${t.result!.substring(0, 60)}…' : t.result!,
                            style: const TextStyle(fontSize: 11.5, color: MeikoColors.text2),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ],
                  ),
                ))
            .toList(),
      ),
    );
  }
}

class _ThinkingDots extends StatefulWidget {
  const _ThinkingDots();
  @override
  State<_ThinkingDots> createState() => _ThinkingDotsState();
}

class _ThinkingDotsState extends State<_ThinkingDots> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final phase = (_controller.value + i * 0.2) % 1.0;
            final dy = -4 * (phase < 0.5 ? phase * 2 : (1 - phase) * 2);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2),
              child: Transform.translate(
                offset: Offset(0, dy),
                child: Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(color: MeikoColors.violetSoft, shape: BoxShape.circle),
                ),
              ),
            );
          }),
        );
      },
    );
  }
}
