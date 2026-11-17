import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

/// Ví dụ client REST API. Thêm dependency `http` trong pubspec.yaml.
/// Android Emulator: http://10.0.2.2:5000
/// Điện thoại thật: http://IP_MAY_CHU_WINDOWS:5000
class ParkingApi {
  ParkingApi({required this.baseUrl, required this.deviceToken});
  final String baseUrl;
  final String deviceToken;

  Map<String, String> get _headers => {'X-Device-Token': deviceToken};

  Future<Map<String, dynamic>> entry({
    required String plate,
    required File image,
  }) => _upload('/api/vehicles/entry', plate, image);

  Future<Map<String, dynamic>> exit({
    required String plate,
    File? image,
  }) => _upload('/api/vehicles/exit', plate, image);

  Future<Map<String, dynamic>> _upload(
      String path, String plate, File? image) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl$path'));
    request.headers.addAll(_headers);
    request.fields['plate'] = plate;
    if (image != null) {
      request.files.add(await http.MultipartFile.fromPath('image', image.path));
    }
    final streamed = await request.send().timeout(const Duration(seconds: 30));
    final response = await http.Response.fromStream(streamed);
    final body = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ParkingApiException(response.statusCode, body);
    }
    return Map<String, dynamic>.from(body as Map);
  }

  Future<List<dynamic>> current({String plate = ''}) async {
    final uri = Uri.parse('$baseUrl/api/vehicles/current')
        .replace(queryParameters: plate.isEmpty ? null : {'plate': plate});
    final response = await http.get(uri, headers: _headers);
    final body = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode != 200) {
      throw ParkingApiException(response.statusCode, body);
    }
    return List<dynamic>.from(body['items'] as List);
  }
}

class ParkingApiException implements Exception {
  ParkingApiException(this.statusCode, this.body);
  final int statusCode;
  final Map<String, dynamic> body;
  @override
  String toString() => 'API $statusCode: ${body['message'] ?? body}';
}
