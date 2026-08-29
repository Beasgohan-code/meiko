import 'dart:math';

import 'package:flutter/material.dart';

import '../providers/meiko_provider.dart';
import '../theme/app_theme.dart';

/// Meiko App — native animated orb avatar, visually consistent with the
/// web app's Three.js orb. Built with a CustomPainter + AnimationController
/// for a lightweight, battery-friendly "living" effect that reacts to
/// [OrbState] (idle / thinking / tool / speaking).
class MeikoOrb extends StatefulWidget {
  final OrbState state;
  final double size;

  const MeikoOrb({super.key, required this.state, this.size = 160});

  @override
  State<MeikoOrb> createState() => _MeikoOrbState();
}

class _MeikoOrbState extends State<MeikoOrb> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(seconds: 6))..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  double get _speed {
    switch (widget.state) {
      case OrbState.thinking:
        return 2.2;
      case OrbState.tool:
        return 3.0;
      case OrbState.speaking:
        return 1.6;
      case OrbState.idle:
        return 0.6;
    }
  }

  double get _amplitude {
    switch (widget.state) {
      case OrbState.thinking:
        return 0.14;
      case OrbState.tool:
        return 0.2;
      case OrbState.speaking:
        return 0.1;
      case OrbState.idle:
        return 0.045;
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final t = _controller.value * 2 * pi * _speed;
        return CustomPaint(
          size: Size(widget.size, widget.size),
          painter: _OrbPainter(t: t, amplitude: _amplitude, state: widget.state),
        );
      },
    );
  }
}

class _OrbPainter extends CustomPainter {
  final double t;
  final double amplitude;
  final OrbState state;

  _OrbPainter({required this.t, required this.amplitude, required this.state});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final baseRadius = size.width / 2 * 0.72;
    final pulse = 1 + sin(t * 1.4) * (state == OrbState.idle ? 0.02 : 0.05);
    final radius = baseRadius * pulse;

    final isActive = state == OrbState.thinking || state == OrbState.tool;
    final colorA = isActive ? MeikoColors.cyan : MeikoColors.violet;
    final colorB = MeikoColors.violetSoft;

    // Outer glow
    final glowPaint = Paint()
      ..shader = RadialGradient(colors: [colorA.withOpacity(0.35), Colors.transparent])
          .createShader(Rect.fromCircle(center: center, radius: radius * 1.9))
      ..blendMode = BlendMode.plus;
    canvas.drawCircle(center, radius * 1.9, glowPaint);

    // Wireframe rings
    final ringPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = colorB.withOpacity(0.25);
    for (int i = 0; i < 3; i++) {
      final ringRadius = radius * (1.15 + i * 0.14);
      final wobble = sin(t * 0.8 + i) * 3;
      canvas.drawCircle(center, ringRadius + wobble, ringPaint);
    }

    // Core orb with organic wobble via a distorted path
    final path = Path();
    const points = 48;
    for (int i = 0; i <= points; i++) {
      final angle = (i / points) * 2 * pi;
      final noise = sin(angle * 3 + t) * cos(angle * 2 - t * 0.8);
      final r = radius * (1 + noise * amplitude);
      final dx = center.dx + r * cos(angle);
      final dy = center.dy + r * sin(angle);
      if (i == 0) {
        path.moveTo(dx, dy);
      } else {
        path.lineTo(dx, dy);
      }
    }
    path.close();

    final corePaint = Paint()
      ..shader = LinearGradient(
        colors: [colorA, colorB],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ).createShader(Rect.fromCircle(center: center, radius: radius));
    canvas.drawPath(path, corePaint);

    // Inner highlight
    final highlightPaint = Paint()
      ..shader = RadialGradient(
        colors: [Colors.white.withOpacity(0.35), Colors.transparent],
        center: const Alignment(-0.3, -0.4),
      ).createShader(Rect.fromCircle(center: center, radius: radius));
    canvas.drawPath(path, highlightPaint);

    // Sparkle particles when using a tool
    if (state == OrbState.tool) {
      final sparklePaint = Paint()..color = Colors.white.withOpacity(0.8);
      for (int i = 0; i < 6; i++) {
        final angle = t * 1.5 + i * (pi / 3);
        final dist = radius * 1.5;
        final p = Offset(center.dx + dist * cos(angle), center.dy + dist * sin(angle));
        canvas.drawCircle(p, 1.6, sparklePaint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _OrbPainter oldDelegate) => true;
}
