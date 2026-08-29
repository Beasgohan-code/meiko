// Basic smoke test for the Meiko app.
import 'package:flutter_test/flutter_test.dart';
import 'package:meiko_app/providers/meiko_provider.dart';
import 'package:meiko_app/main.dart';

void main() {
  testWidgets('Meiko app builds without crashing', (WidgetTester tester) async {
    final provider = MeikoProvider(backendUrl: 'http://localhost:8000', userId: 'test-user');
    await tester.pumpWidget(MeikoApp(meikoProvider: provider));
    expect(find.text('Meiko Agent'), findsOneWidget);
  });
}
