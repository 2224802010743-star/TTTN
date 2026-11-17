import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:camera/camera.dart' as cam;
import 'package:image_picker/image_picker.dart';

import 'parking_api.dart';

// Flutter Web/Chrome trên cùng máy với Flask:
const String kApiBaseUrl = 'http://127.0.0.1:5000';
// Lấy giá trị API_DEVICE_TOKEN trong backend/.env. Không chia sẻ token này.
const String kDeviceToken = 'ru6tYLoVGwkTAyofTMudM3TrGgd_3V3Nv5Zoe3wriLw';

void main() => runApp(const ParkingApp());

class ParkingApp extends StatelessWidget {
  const ParkingApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Quản lý bãi xe',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorSchemeSeed: const Color(0xff1769aa),
      useMaterial3: true,
    ),
    home: const ParkingHomePage(),
  );
}

class ParkingHomePage extends StatefulWidget {
  const ParkingHomePage({super.key});

  @override
  State<ParkingHomePage> createState() => _ParkingHomePageState();
}

class _ParkingHomePageState extends State<ParkingHomePage>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 3, vsync: this);
  final _plateController = TextEditingController();
  final _picker = ImagePicker();
  late final ParkingApi _api = ParkingApi(
    baseUrl: kApiBaseUrl,
    deviceToken: kDeviceToken,
  );

  XFile? _photo;
  Uint8List? _photoBytes;
  bool _busy = false;
  String _message =
      'Chọn/chụp ảnh xe, nhập biển số đã xác nhận rồi ghi nhận vào/ra.';
  List<dynamic> _current = [];

  @override
  void dispose() {
    _tabs.dispose();
    _plateController.dispose();
    super.dispose();
  }

  Future<void> _takePhoto() async {
    cam.CameraController? controller;
    try {
      // camera plugin mở luồng webcam trực tiếp trên Chrome (getUserMedia).
      final cameras = await cam.availableCameras();
      if (cameras.isEmpty) {
        _notify(
          'Không tìm thấy camera. Kiểm tra camera đang kết nối và quyền Chrome.',
        );
        return;
      }
      final selected = cameras.cast<cam.CameraDescription?>().firstWhere(
        (c) => c?.lensDirection == cam.CameraLensDirection.back,
        orElse: () => cameras.first,
      )!;
      controller = cam.CameraController(
        selected,
        cam.ResolutionPreset.high,
        enableAudio: false,
      );
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      final shot = await showDialog<XFile>(
        context: context,
        barrierDismissible: false,
        builder: (_) => _CameraCaptureDialog(controller: controller!),
      );
      await controller.dispose();
      controller = null;
      if (shot == null) return;
      final bytes = await shot.readAsBytes();
      if (!mounted) return;
      setState(() {
        _photo = shot;
        _photoBytes = bytes;
      });
    } catch (e) {
      if (controller != null) {
        try {
          await controller.dispose();
        } catch (_) {}
      }
      _notify(
        'Không mở được webcam: $e. Hãy cấp quyền Camera cho Chrome hoặc chọn ảnh từ máy.',
      );
    }
  }

  Future<void> _choosePhoto() async {
    try {
      final shot = await _picker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 85,
        maxWidth: 1920,
      );
      if (shot == null) return;
      final bytes = await shot.readAsBytes();
      if (!mounted) return;
      setState(() {
        _photo = shot;
        _photoBytes = bytes;
      });
    } catch (e) {
      _notify('Không chọn được ảnh: $e');
    }
  }

  void _notify(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _recognizePlate() async {
    if (_photo == null) {
      _notify('Vui lòng chụp hoặc chọn ảnh xe trước khi nhận diện.');
      return;
    }
    if (kDeviceToken.startsWith('REPLACE_') || kDeviceToken.length < 24) {
      _notify('Hãy cấu hình kDeviceToken trong main.dart trước.');
      return;
    }

    setState(() {
      _busy = true;
      _message = 'Đang phát hiện biển số bằng YOLO và đọc ký tự bằng OCR...';
    });
    try {
      final result = await _api.recognizePlate(image: _photo!);
      final plate = (result['plate'] ?? '').toString();
      final yolo = (result['yolo_confidence'] as num?)?.toDouble();
      final ocr = (result['ocr_confidence'] as num?)?.toDouble();
      if (!mounted) return;
      setState(() {
        if (plate.isNotEmpty) {
          _plateController.value = TextEditingValue(
            text: plate,
            selection: TextSelection.collapsed(offset: plate.length),
          );
        }
        _message =
            'Biển số AI dự đoán: ${plate.isEmpty ? '(chưa đọc được)' : plate}'
            '\nYOLO: ${yolo == null ? '—' : (yolo * 100).toStringAsFixed(1) + '%'}'
            '\nOCR: ${ocr == null ? '—' : (ocr * 100).toStringAsFixed(1) + '%'}'
            '\nHãy kiểm tra/chỉnh biển số trước khi xác nhận.';
      });
      _notify(
        plate.isEmpty
            ? 'AI chưa đọc được biển số. Bạn có thể nhập thủ công.'
            : 'AI dự đoán $plate. Hãy kiểm tra lại trước khi lưu.',
      );
    } on ParkingApiException catch (e) {
      if (mounted) {
        setState(
          () => _message =
              'AI chưa nhận diện được: ${e.body['message'] ?? e.body}',
        );
      }
    } catch (e) {
      if (mounted) setState(() => _message = 'Không gọi được dịch vụ AI: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit(bool isEntry) async {
    final plate = _plateController.text.trim();
    if (plate.isEmpty) {
      _notify('Vui lòng nhập biển số xe.');
      return;
    }
    if (_photo == null) {
      _notify('Vui lòng chụp hoặc chọn ảnh xe trước khi xác nhận.');
      return;
    }
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
      if (!mounted) return;
      setState(() {
        _message =
            '${result['message'] ?? 'Thành công'}'
            '${session == null ? '' : '\nBiển số: ${session['plate']}'}';
        _photo = null;
        _photoBytes = null;
        _plateController.clear();
      });
      _notify(result['message']?.toString() ?? 'Thành công');
      if (!isEntry) await _loadCurrent();
    } on ParkingApiException catch (e) {
      if (mounted) {
        setState(() => _message = 'Lỗi API: ${e.body['message'] ?? e.body}');
      }
    } catch (e) {
      if (mounted) setState(() => _message = 'Không kết nối được máy chủ: $e');
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
      bottom: TabBar(
        controller: _tabs,
        tabs: const [
          Tab(text: 'Xe vào', icon: Icon(Icons.login)),
          Tab(text: 'Xe ra', icon: Icon(Icons.logout)),
          Tab(text: 'Đang gửi', icon: Icon(Icons.local_parking)),
        ],
      ),
    ),
    body: TabBarView(
      controller: _tabs,
      children: [
        _operationView(isEntry: true),
        _operationView(isEntry: false),
        _currentView(),
      ],
    ),
  );

  Widget _operationView({required bool isEntry}) => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      Text(
        isEntry ? 'Ghi nhận xe vào' : 'Ghi nhận xe ra',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 12),
      TextField(
        controller: _plateController,
        textCapitalization: TextCapitalization.characters,
        decoration: const InputDecoration(
          labelText: 'Biển số xe',
          hintText: 'Ví dụ: 51A12345',
          border: OutlineInputBorder(),
        ),
      ),
      const SizedBox(height: 12),
      Wrap(
        spacing: 10,
        runSpacing: 8,
        children: [
          OutlinedButton.icon(
            onPressed: _busy ? null : _takePhoto,
            icon: const Icon(Icons.camera_alt),
            label: const Text('Mở camera để chụp'),
          ),
          OutlinedButton.icon(
            onPressed: _busy ? null : _choosePhoto,
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('Chọn ảnh từ máy'),
          ),
        ],
      ),
      if (_photoBytes != null) ...[
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Image.memory(_photoBytes!, height: 210, fit: BoxFit.cover),
        ),
        TextButton.icon(
          onPressed: _busy
              ? null
              : () => setState(() {
                  _photo = null;
                  _photoBytes = null;
                }),
          icon: const Icon(Icons.delete_outline),
          label: const Text('Bỏ ảnh / chọn lại'),
        ),
      ],
      const SizedBox(height: 12),
      FilledButton.tonalIcon(
        onPressed: _busy ? null : _recognizePlate,
        icon: const Icon(Icons.document_scanner),
        label: const Text('AI nhận diện biển số'),
      ),
      const SizedBox(height: 8),
      FilledButton.icon(
        onPressed: _busy ? null : () => _submit(isEntry),
        icon: _busy
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : Icon(isEntry ? Icons.login : Icons.logout),
        label: Text(isEntry ? 'Xác nhận xe vào' : 'Xác nhận xe ra'),
      ),
      const SizedBox(height: 16),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Text(_message),
        ),
      ),
      const SizedBox(height: 8),
      const Text(
        'AI chỉ đề xuất biển số từ ảnh. Nhân viên phải kiểm tra/chỉnh biển số trước khi xác nhận lưu xe.',
      ),
    ],
  );

  Widget _currentView() => RefreshIndicator(
    onRefresh: _loadCurrent,
    child: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Xe đang gửi (${_current.length})',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ),
            IconButton(
              onPressed: _busy ? null : _loadCurrent,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        if (_current.isEmpty)
          const Padding(
            padding: EdgeInsets.all(28),
            child: Center(
              child: Text(
                'Chưa tải dữ liệu hoặc không có xe đang gửi. Kéo xuống để làm mới.',
              ),
            ),
          ),
        for (final row in _current)
          Card(
            child: ListTile(
              leading: const CircleAvatar(child: Icon(Icons.directions_car)),
              title: Text(
                '${row['plate'] ?? ''}',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              subtitle: Text('Giờ vào: ${row['entry_time'] ?? '—'}'),
            ),
          ),
      ],
    ),
  );
}

class _CameraCaptureDialog extends StatefulWidget {
  const _CameraCaptureDialog({required this.controller});
  final cam.CameraController controller;

  @override
  State<_CameraCaptureDialog> createState() => _CameraCaptureDialogState();
}

class _CameraCaptureDialogState extends State<_CameraCaptureDialog> {
  bool _capturing = false;
  String? _error;

  Future<void> _capture() async {
    if (_capturing) return;
    setState(() {
      _capturing = true;
      _error = null;
    });
    try {
      final shot = await widget.controller.takePicture();
      if (mounted) Navigator.of(context).pop<XFile>(shot);
    } catch (e) {
      if (mounted)
        setState(() {
          _capturing = false;
          _error = 'Không chụp được ảnh: $e';
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final preview = AspectRatio(
      aspectRatio: widget.controller.value.aspectRatio,
      child: cam.CameraPreview(widget.controller),
    );
    return AlertDialog(
      title: const Text('Chụp ảnh xe'),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760, maxHeight: 560),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              preview,
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _capturing
              ? null
              : () => Navigator.of(context).pop<XFile>(),
          child: const Text('Hủy'),
        ),
        FilledButton.icon(
          onPressed: _capturing ? null : _capture,
          icon: _capturing
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.camera),
          label: Text(_capturing ? 'Đang chụp...' : 'Chụp ảnh'),
        ),
      ],
    );
  }
}
