<?php
// RideFlow Error Handler
// Gestion centralisée des erreurs et logging

class RideFlowErrorHandler {
    private static $logFile = '/var/log/apache2/rideflow.log';
    
    public static function init() {
        // Configure error reporting
        error_reporting(E_ALL);
        ini_set('display_errors', 0);
        ini_set('log_errors', 1);
        ini_set('error_log', self::$logFile);
        
        // Set custom error handlers
        set_error_handler([self::class, 'handleError']);
        set_exception_handler([self::class, 'handleException']);
        register_shutdown_function([self::class, 'handleShutdown']);
    }
    
    public static function handleError($severity, $message, $file, $line) {
        if (!(error_reporting() & $severity)) {
            return false;
        }
        
        $error = [
            'type' => 'Error',
            'severity' => self::getSeverityName($severity),
            'message' => $message,
            'file' => $file,
            'line' => $line,
            'timestamp' => date('Y-m-d H:i:s'),
            'user_ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
            'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown'
        ];
        
        self::logError($error);
        
        // Don't execute PHP's internal error handler
        return true;
    }
    
    public static function handleException($exception) {
        $error = [
            'type' => 'Exception',
            'class' => get_class($exception),
            'message' => $exception->getMessage(),
            'file' => $exception->getFile(),
            'line' => $exception->getLine(),
            'trace' => $exception->getTraceAsString(),
            'timestamp' => date('Y-m-d H:i:s'),
            'user_ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
            'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown'
        ];
        
        self::logError($error);
        
        // Send JSON response for AJAX requests
        if (self::isAjaxRequest()) {
            header('Content-Type: application/json');
            echo json_encode([
                'success' => false,
                'error' => 'Une erreur interne s\'est produite. Veuillez réessayer.',
                'error_id' => self::generateErrorId()
            ]);
        } else {
            self::showErrorPage();
        }
    }
    
    public static function handleShutdown() {
        $error = error_get_last();
        
        if ($error && in_array($error['type'], [E_ERROR, E_CORE_ERROR, E_COMPILE_ERROR, E_PARSE])) {
            $errorInfo = [
                'type' => 'Fatal Error',
                'message' => $error['message'],
                'file' => $error['file'],
                'line' => $error['line'],
                'timestamp' => date('Y-m-d H:i:s'),
                'user_ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
                'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown'
            ];
            
            self::logError($errorInfo);
            
            if (self::isAjaxRequest()) {
                header('Content-Type: application/json');
                echo json_encode([
                    'success' => false,
                    'error' => 'Erreur critique du serveur',
                    'error_id' => self::generateErrorId()
                ]);
            } else {
                self::showErrorPage();
            }
        }
    }
    
    private static function logError($error) {
        $logEntry = sprintf(
            "[%s] %s: %s in %s on line %d\n",
            $error['timestamp'],
            $error['type'],
            $error['message'],
            $error['file'],
            $error['line']
        );
        
        // Add additional context for exceptions
        if (isset($error['trace'])) {
            $logEntry .= "Stack trace:\n" . $error['trace'] . "\n";
        }
        
        $logEntry .= "User IP: " . $error['user_ip'] . "\n";
        $logEntry .= "User Agent: " . $error['user_agent'] . "\n";
        $logEntry .= str_repeat("-", 80) . "\n";
        
        $logDir = dirname(self::$logFile);
        if (!is_dir($logDir)) {
            mkdir($logDir, 0777, true);
        }
        
        file_put_contents(self::$logFile, $logEntry, FILE_APPEND | LOCK_EX);
    }
    
    public static function logCustom($level, $message, $context = []) {
        $logEntry = sprintf(
            "[%s] %s: %s\n",
            date('Y-m-d H:i:s'),
            strtoupper($level),
            $message
        );
        
        if (!empty($context)) {
            $logEntry .= "Context: " . json_encode($context, JSON_UNESCAPED_UNICODE) . "\n";
        }
        
        $logEntry .= str_repeat("-", 40) . "\n";
        
        $logDir = dirname(self::$logFile);
        if (!is_dir($logDir)) {
            mkdir($logDir, 0777, true);
        }
        
        file_put_contents(self::$logFile, $logEntry, FILE_APPEND | LOCK_EX);
    }
    
    private static function getSeverityName($severity) {
        $severities = [
            E_ERROR => 'E_ERROR',
            E_WARNING => 'E_WARNING',
            E_PARSE => 'E_PARSE',
            E_NOTICE => 'E_NOTICE',
            E_CORE_ERROR => 'E_CORE_ERROR',
            E_CORE_WARNING => 'E_CORE_WARNING',
            E_COMPILE_ERROR => 'E_COMPILE_ERROR',
            E_COMPILE_WARNING => 'E_COMPILE_WARNING',
            E_USER_ERROR => 'E_USER_ERROR',
            E_USER_WARNING => 'E_USER_WARNING',
            E_USER_NOTICE => 'E_USER_NOTICE',
            E_STRICT => 'E_STRICT',
            E_RECOVERABLE_ERROR => 'E_RECOVERABLE_ERROR',
            E_DEPRECATED => 'E_DEPRECATED',
            E_USER_DEPRECATED => 'E_USER_DEPRECATED'
        ];
        
        return $severities[$severity] ?? 'UNKNOWN';
    }
    
    private static function isAjaxRequest() {
        return isset($_SERVER['HTTP_X_REQUESTED_WITH']) && 
               strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) === 'xmlhttprequest';
    }
    
    private static function generateErrorId() {
        return sprintf(
            '%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
            mt_rand(0, 0xffff), mt_rand(0, 0xffff),
            mt_rand(0, 0xffff),
            mt_rand(0, 0x0fff) | 0x4000,
            mt_rand(0, 0x3fff) | 0x8000,
            mt_rand(0, 0xffff), mt_rand(0, 0xffff), mt_rand(0, 0xffff)
        );
    }
    
    private static function showErrorPage() {
        http_response_code(500);
        ?>
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Erreur - RideFlow</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
            <style>
                body { background-color: #f8f9fa; }
                .error-container { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
                .error-card { max-width: 500px; width: 100%; border-radius: 12px; }
            </style>
        </head>
        <body>
            <div class="error-container">
                <div class="card shadow error-card">
                    <div class="card-header bg-danger text-white text-center">
                        <h3 class="mb-0"><i class="bi bi-exclamation-circle-fill me-2"></i>Erreur du Serveur</h3>
                    </div>
                    <div class="card-body text-center">
                        <p class="card-text">
                            Nous rencontrons actuellement des difficultés techniques.
                            Veuillez réessayer dans quelques instants.
                        </p>
                        <p class="small text-muted mb-4">
                            ID d'erreur: <?= self::generateErrorId() ?><br>
                            Timestamp: <?= date('Y-m-d H:i:s') ?>
                        </p>
                        <a href="/" class="btn btn-primary">
                            <i class="bi bi-house"></i> Retour à l'accueil
                        </a>
                        <button onclick="location.reload()" class="btn btn-outline-secondary">
                            <i class="bi bi-arrow-clockwise"></i> Réessayer
                        </button>
                    </div>
                </div>
            </div>
        </body>
        </html>
        <?php
        exit;
    }
}

// Validation and Input Sanitization Helper
class InputValidator {
    public static function validateGPXFile($file) {
        if (!isset($file) || $file['error'] !== UPLOAD_ERR_OK) {
            throw new InvalidArgumentException('Fichier GPX non valide ou manquant');
        }
        
        // Check file size (max 50MB)
        if ($file['size'] > 50 * 1024 * 1024) {
            throw new InvalidArgumentException('Fichier trop volumineux (max 50MB)');
        }
        
        // Check file extension
        $extension = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
        if ($extension !== 'gpx') {
            throw new InvalidArgumentException('Seuls les fichiers GPX sont acceptés');
        }
        
        // Check MIME type
        $finfo = finfo_open(FILEINFO_MIME_TYPE);
        $mimeType = finfo_file($finfo, $file['tmp_name']);
        finfo_close($finfo);
        
        $allowedMimes = ['application/xml', 'text/xml', 'application/gpx+xml'];
        if (!in_array($mimeType, $allowedMimes)) {
            throw new InvalidArgumentException('Type de fichier non autorisé');
        }
        
        return true;
    }
    
    public static function sanitizeString($input, $maxLength = 255) {
        if (!is_string($input)) {
            return '';
        }
        
        $sanitized = trim($input);
        $sanitized = htmlspecialchars($sanitized, ENT_QUOTES | ENT_HTML5, 'UTF-8');
        
        if ($maxLength > 0) {
            $sanitized = substr($sanitized, 0, $maxLength);
        }
        
        return $sanitized;
    }
    
    public static function validateDateTime($datetime) {
        if (empty($datetime)) {
            throw new InvalidArgumentException('Date/heure requise');
        }
        
        $date = DateTime::createFromFormat('Y-m-d\TH:i', $datetime);
        if (!$date) {
            throw new InvalidArgumentException('Format de date/heure invalide');
        }
        
        // Check if date is not too far in the past or future
        $now = new DateTime();
        $minDate = clone $now;
        $minDate->sub(new DateInterval('P1D')); // 1 day ago
        $maxDate = clone $now;
        $maxDate->add(new DateInterval('P7D')); // 7 days ahead
        
        if ($date < $minDate || $date > $maxDate) {
            throw new InvalidArgumentException('Date hors des limites autorisées (1 jour avant à 7 jours après)');
        }
        
        return $date->format('Y-m-d H:i:s');
    }
}

function fetchWeatherData($segments, $datetime) {
    $centerLat = array_sum(array_column(array_column($segments, 'start'), 'lat')) / count($segments);
    $centerLon = array_sum(array_column(array_column($segments, 'start'), 'lon')) / count($segments);
    
    $url = "https://api.open-meteo.com/v1/forecast";
    $params = [
        'latitude' => $centerLat,
        'longitude' => $centerLon,
        'hourly' => 'temperature_2m,wind_speed_10m,wind_direction_10m,precipitation_probability',
        'timezone' => 'Europe/Paris',
        'start_date' => date('Y-m-d', strtotime($datetime)),
        'end_date' => date('Y-m-d', strtotime($datetime))
    ];
    
    $query = http_build_query($params);
    $fullUrl = "$url?$query";
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $fullUrl);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
    $response = curl_exec($ch);
    
    if (curl_errno($ch)) {
        throw new Exception('Erreur API Open-Meteo: ' . curl_error($ch));
    }
    
    curl_close($ch);
    
    $data = json_decode($response, true);
    
    if (!$data || !isset($data['hourly'])) {
        throw new Exception('Données météo invalides');
    }
    
    return $data['hourly'];
}

// Initialize error handling
RideFlowErrorHandler::init();
?>