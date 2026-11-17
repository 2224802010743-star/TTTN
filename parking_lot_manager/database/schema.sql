CREATE DATABASE IF NOT EXISTS parking_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'parking_app'@'localhost'
  IDENTIFIED BY 'CHANGE_ME_DB_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON parking_db.* TO 'parking_app'@'localhost';
FLUSH PRIVILEGES;

USE parking_db;

CREATE TABLE IF NOT EXISTS vehicle_sessions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  plate VARCHAR(20) NOT NULL,
  status ENUM('IN','EXITED') NOT NULL DEFAULT 'IN',
  active_plate VARCHAR(20) GENERATED ALWAYS AS (CASE WHEN status = 'IN' THEN plate ELSE NULL END) STORED,
  entry_time DATETIME NOT NULL,
  exit_time DATETIME NULL,
  entry_image VARCHAR(255) NOT NULL,
  exit_image VARCHAR(255) NULL,
  entry_source VARCHAR(32) NOT NULL DEFAULT 'flutter',
  exit_source VARCHAR(32) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_plate (plate),
  INDEX idx_status_entry (status, entry_time),
  INDEX idx_entry_time (entry_time),
  UNIQUE KEY uq_active_plate (active_plate)
) ENGINE=InnoDB;
