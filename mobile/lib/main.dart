import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/meiko_provider.dart';
import 'screens/chat_screen.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final meikoProvider = await MeikoProvider.create();
  runApp(MeikoApp(meikoProvider: meikoProvider));
}

class MeikoApp extends StatelessWidget {
  final MeikoProvider meikoProvider;
  const MeikoApp({super.key, required this.meikoProvider});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: meikoProvider,
      child: MaterialApp(
        title: 'Meiko',
        debugShowCheckedModeBanner: false,
        theme: buildMeikoTheme(),
        home: const ChatScreen(),
      ),
    );
  }
}
