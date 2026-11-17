import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

/// REST client dùng được trên Flutter Web và Android.
class ParkingApi {
  ParkingApi({required this.baseUrl, required this.deviceToken});

  final String baseUrl;
  final String deviceToken;

  Map<String, String> get _headers => {'X-Device-Token': deviceToken};

  Future<Map<String, dynamic>> recognizePlate({required XFile image}) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/plates/recognize'),
    );
    request.headers.addAll(_headers);
    request.files.add(http.MultipartFile.fromBytes(
      'image',
      await image.readAsBytes(),
      filename: image.name,
    ));

    final streamed = await request.send().timeout(const Duration(seconds: 260));
    final response = await http.Response.fromStream(streamed);
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    final body = Map<String, dynamic>.from(decoded as Map);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ParkingApiException(response.statusCode, body);
    }
    return body;
  }

  Future<Map<String, dynamic>> entry({
    required String plate,
    required XFile image,
  }) => _upload('/api/vehicles/entry', plate, image);

  Future<Map<String, dynamic>> exit({
    required String plate,
    required XFile image,
  }) => _upload('/api/vehicles/exit', plate, image);

  Future<Map<String, dynamic>> _upload(
    String path,
    String plate,
    XFile image,
  ) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl$path'));
    request.headers.addAll(_headers);
    request.fields['plate'] = plate;
    request.files.add(http.MultipartFile.fromBytes(
      'image',
      await image.readAsBytes(),
      filename: image.name,
    ));

    final streamed = await request.send().timeout(const Duration(seconds: 45));
    final response = await http.Response.fromStream(streamed);
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    final body = Map<String, dynamic>.from(decoded as Map);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ParkingApiException(response.statusCode, body);
    }
    return body;
  }

  Future<List<dynamic>> current({String plate = ''}) async {
    final uri = Uri.parse('$baseUrl/api/vehicles/current').replace(
      queryParameters: plate.trim().isEmpty ? null : {'plate': plate.trim()},
    );
    final response = await http.get(uri, headers: _headers)
        .timeout(const Duration(seconds: 20));
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    final body = Map<String, dynamic>.from(decoded as Map);
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
