import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'parking_api.dart';

// Emulator Android -> 10.0.2.2. Điện thoại thật -> IPv4 máy Windows.
// Thay token dùng thử; không nhúng token dùng chung vào app phát hành thực tế.
const String kApiBaseUrl = 'http://10.0.2.2:5000';
const String kDeviceToken = 'REPLACE_WITH_YOUR_LONG_DEVICE_TOKEN';

void main() => runApp(const ParkingApp());

class ParkingApp extends StatelessWidget {
  const ParkingApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Quản lý bãi xe',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(colorSchemeSeed: const Color(0xff1769aa), useMaterial3: true),
        home: const ParkingHomePage(),
      );
}

class ParkingHomePage extends StatefulWidget {
  const ParkingHomePage({super.key});
  @override
  State<ParkingHomePage> createState() => _ParkingHomePageState();
}

class _ParkingHomePageState extends State<ParkingHomePage> with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 3, vsync: this);
  final _plateController = TextEditingController();
  final _picker = ImagePicker();
  late final ParkingApi _api = ParkingApi(baseUrl: kApiBaseUrl, deviceToken: kDeviceToken);
  File? _photo;
  bool _busy = false;
  String _message = 'Chụp ảnh xe, nhập biển số đã xác nhận rồi ghi nhận vào/ra.';
  List<dynamic> _current = [];

  @override
  void dispose() {
    _tabs.dispose();
    _plateController.dispose();
    super.dispose();
  }

  Future<void> _takePhoto() async {
    try {
      final shot = await _picker.pickImage(source: ImageSource.camera, imageQuality: 85, maxWidth: 1920);
      if (shot != null && mounted) setState(() => _photo = File(shot.path));
    } catch (e) {
      _notify('Không mở được camera: $e');
    }
  }

  void _notify(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _submit(bool isEntry) async {
    final plate = _plateController.text.trim();
    if (plate.isEmpty) { _notify('Vui lòng nhập biển số xe.'); return; }
    if (_photo == null) { _notify('Vui lòng chụp ảnh xe trước khi xác nhận.'); return; }
    if (kDeviceToken.startsWith('REPLACE_') || kDeviceToken.length < 24) {
      _notify('Hãy cấu hình kDeviceToken trong main.dart trước.');
      return;
    }
    setState(() => _busy = true);
    try {
      final result = isEntry
          ? await _api.entry(plate: plate, image: _photo!)
          : await _api.exit(plate: plate, image: _photo!);
      final session = result['session'] as Map<String, dynamic>?;
      setState(() {
        _message = '${result['message'] ?? 'Thành công'}${session == null ? '' : '\nBiển số: ${session['plate']}'}';
        _photo = null;
        _plateController.clear();
      });
      _notify(result['message']?.toString() ?? 'Thành công');
      if (!isEntry) await _loadCurrent();
    } on ParkingApiException catch (e) {
      setState(() => _message = 'Lỗi API: ${e.body['message'] ?? e.body}');
    } catch (e) {
      setState(() => _message = 'Không kết nối được máy chủ: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _loadCurrent() async {
    if (kDeviceToken.startsWith('REPLACE_') || kDeviceToken.length < 24) {
      _notify('Hãy cấu hình kDeviceToken trong main.dart trước.');
      return;
    }
    setState(() => _busy = true);
    try {
      final data = await _api.current();
      if (mounted) setState(() => _current = data);
    } catch (e) {
      _notify('Không tải được danh sách xe: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Quản lý bãi giữ xe'),
          bottom: TabBar(controller: _tabs, tabs: const [
            Tab(text: 'Xe vào', icon: Icon(Icons.login)),
            Tab(text: 'Xe ra', icon: Icon(Icons.logout)),
            Tab(text: 'Đang gửi', icon: Icon(Icons.local_parking)),
          ]),
        ),
        body: TabBarView(controller: _tabs, children: [
          _operationView(isEntry: true),
          _operationView(isEntry: false),
          _currentView(),
        ]),
      );

  Widget _operationView({required bool isEntry}) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(isEntry ? 'Ghi nhận xe vào' : 'Ghi nhận xe ra', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          TextField(
            controller: _plateController,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(labelText: 'Biển số xe', hintText: 'Ví dụ: 51A12345', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(onPressed: _busy ? null : _takePhoto, icon: const Icon(Icons.camera_alt), label: const Text('Chụp ảnh xe')),
          if (_photo != null) ...[
            const SizedBox(height: 12),
            ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.file(_photo!, height: 210, fit: BoxFit.cover)),
            TextButton.icon(onPressed: _busy ? null : () => setState(() => _photo = null), icon: const Icon(Icons.delete_outline), label: const Text('Chụp lại')),
          ],
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: _busy ? null : () => _submit(isEntry),
            icon: _busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : Icon(isEntry ? Icons.login : Icons.logout),
            label: Text(isEntry ? 'Xác nhận xe vào' : 'Xác nhận xe ra'),
          ),
          const SizedBox(height: 16),
          Card(child: Padding(padding: const EdgeInsets.all(12), child: Text(_message))),
          const SizedBox(height: 8),
          const Text('Ghi chú: bản mẫu yêu cầu nhân viên nhập/xác nhận biển số. AI nhận diện tự động cần được tích hợp và kiểm thử riêng.'),
        ],
      );

  Widget _currentView() => RefreshIndicator(
        onRefresh: _loadCurrent,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Row(children: [Expanded(child: Text('Xe đang gửi (${_current.length})', style: Theme.of(context).textTheme.headlineSmall)), IconButton(onPressed: _busy ? null : _loadCurrent, icon: const Icon(Icons.refresh))]),
            if (_current.isEmpty) const Padding(padding: EdgeInsets.all(28), child: Center(child: Text('Chưa tải dữ liệu hoặc không có xe đang gửi. Kéo xuống để làm mới.'))),
            for (final row in _current)
              Card(child: ListTile(
                leading: const CircleAvatar(child: Icon(Icons.directions_car)),
                title: Text('${row['plate'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Text('Giờ vào: ${row['entry_time'] ?? '—'}'),
                trailing: const Icon(Icons.chevron_right),
              )),
          ],
        ),
      );
}
