<?php
/**
 * RideFlow Backend - Version Refactorisée
 * Optimiseur de parcours cyclistes basé sur les conditions de vent
 */

// Configuration
ini_set('display_errors', 0);
ini_set('log_errors', 1);
ini_set('error_log', '/var/www/html/logs/rideflow.log');

// Headers CORS
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-Requested-With');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Router principal
try {
    $action = getAction();
    
    switch ($action) {
        case 'parse_gpx':
            handleGpxParsing();
            break;
        case 'analyze_wind':
            handleWindAnalysis();
            break;
        default:
            throw new InvalidArgumentException('Action non valide: ' . $action);
    }
} catch (Exception $e) {
    error_log("Erreur RideFlow: " . $e->getMessage());
    http_response_code(400);
    echo json_encode([
        'success' => false, 
        'error' => $e->getMessage()
    ], JSON_UNESCAPED_UNICODE);
}

/**
 * Extraction de l'action depuis la requête
 */
function getAction(): string {
    $contentType = $_SERVER['CONTENT_TYPE'] ?? '';
    
    if (strpos($contentType, 'application/json') !== false) {
        $input = json_decode(file_get_contents('php://input'), true) ?? [];
        return $input['action'] ?? '';
    }
    
    return $_POST['action'] ?? $_GET['action'] ?? '';
}

/**
 * Gestion du parsing GPX
 */
function handleGpxParsing(): void {
    if (!isset($_FILES['gpx']) || $_FILES['gpx']['error'] !== UPLOAD_ERR_OK) {
        throw new RuntimeException('Erreur lors du téléchargement du fichier GPX');
    }

    $gpxContent = file_get_contents($_FILES['gpx']['tmp_name']);
    if ($gpxContent === false) {
        throw new RuntimeException('Impossible de lire le fichier GPX');
    }

    $points = parseGpxContent($gpxContent);
    $points = simplifyRoute($points); // Optimisation pour éviter la surcharge
    $segments = calculateSegments($points);
    $totalDistance = array_sum(array_column($segments, 'distance'));

    respondSuccess([
        'name' => $_FILES['gpx']['name'],
        'points' => $points,
        'segments' => $segments,
        'total_distance' => round($totalDistance, 2),
        'total_points' => count($points),
        'route_info' => analyzeRouteDirection($segments)
    ]);
}

/**
 * Parser le contenu GPX et extraire les points
 */
function parseGpxContent(string $gpxContent): array {
    libxml_use_internal_errors(true);
    $xml = simplexml_load_string($gpxContent);
    
    if ($xml === false) {
        $errors = implode('; ', array_map(fn($e) => $e->message, libxml_get_errors()));
        libxml_clear_errors();
        throw new InvalidArgumentException('Fichier GPX invalide: ' . $errors);
    }

    $points = [];
    
    // Priorité: tracks > routes > waypoints
    $extractors = [
        fn() => extractTrackPoints($xml),
        fn() => extractRoutePoints($xml),
        fn() => extractWaypoints($xml)
    ];

    foreach ($extractors as $extractor) {
        $points = $extractor();
        if (!empty($points)) break;
    }

    if (count($points) < 2) {
        throw new InvalidArgumentException('Fichier GPX sans données de parcours valides (minimum 2 points requis)');
    }

    return $points;
}

/**
 * Extraction des points de track
 */
function extractTrackPoints(SimpleXMLElement $xml): array {
    $points = [];
    
    if (isset($xml->trk)) {
        foreach ($xml->trk as $track) {
            if (isset($track->trkseg)) {
                foreach ($track->trkseg as $segment) {
                    if (isset($segment->trkpt)) {
                        foreach ($segment->trkpt as $pt) {
                            if (isset($pt['lat'], $pt['lon'])) {
                                $points[] = [
                                    'lat' => (float)$pt['lat'], 
                                    'lon' => (float)$pt['lon']
                                ];
                            }
                        }
                    }
                }
            }
        }
    }
    
    return $points;
}

/**
 * Extraction des points de route
 */
function extractRoutePoints(SimpleXMLElement $xml): array {
    $points = [];
    
    if (isset($xml->rte)) {
        foreach ($xml->rte as $route) {
            if (isset($route->rtept)) {
                foreach ($route->rtept as $pt) {
                    if (isset($pt['lat'], $pt['lon'])) {
                        $points[] = [
                            'lat' => (float)$pt['lat'], 
                            'lon' => (float)$pt['lon']
                        ];
                    }
                }
            }
        }
    }
    
    return $points;
}

/**
 * Extraction des waypoints
 */
function extractWaypoints(SimpleXMLElement $xml): array {
    $points = [];
    
    if (isset($xml->wpt)) {
        foreach ($xml->wpt as $pt) {
            if (isset($pt['lat'], $pt['lon'])) {
                $points[] = [
                    'lat' => (float)$pt['lat'], 
                    'lon' => (float)$pt['lon']
                ];
            }
        }
    }
    
    return $points;
}

/**
 * Simplification intelligente de la route
 */
function simplifyRoute(array $points, int $maxPoints = 200, float $minDistance = 0.1): array {
    if (count($points) <= $maxPoints) {
        return $points;
    }
    
    $simplified = [$points[0]]; // Premier point
    $step = max(1, floor(count($points) / $maxPoints));
    
    for ($i = $step; $i < count($points) - 1; $i += $step) {
        $lastPoint = end($simplified);
        $distance = calculateDistance(
            $lastPoint['lat'], $lastPoint['lon'],
            $points[$i]['lat'], $points[$i]['lon']
        );
        
        if ($distance >= $minDistance) {
            $simplified[] = $points[$i];
        }
    }
    
    $simplified[] = $points[count($points) - 1]; // Dernier point
    
    error_log(sprintf("Simplification: %d -> %d points", count($points), count($simplified)));
    
    return $simplified;
}

/**
 * Calculer les segments du parcours
 */
function calculateSegments(array $points): array {
    $segments = [];
    
    for ($i = 0; $i < count($points) - 1; $i++) {
        $p1 = $points[$i];
        $p2 = $points[$i + 1];
        
        $segments[] = [
            'id' => $i,
            'start' => $p1,
            'end' => $p2,
            'distance' => round(calculateDistance($p1['lat'], $p1['lon'], $p2['lat'], $p2['lon']), 3),
            'bearing' => round(calculateBearing($p1['lat'], $p1['lon'], $p2['lat'], $p2['lon']), 1),
            'bearing_text' => bearingToText(calculateBearing($p1['lat'], $p1['lon'], $p2['lat'], $p2['lon']))
        ];
    }
    
    return $segments;
}

/**
 * Analyser la direction générale du parcours
 */
function analyzeRouteDirection(array $segments): array {
    if (empty($segments)) {
        return ['type' => 'unknown', 'description' => 'Parcours indéterminé'];
    }
    
    $startPoint = $segments[0]['start'];
    $endPoint = end($segments)['end'];
    $distance = calculateDistance($startPoint['lat'], $startPoint['lon'], $endPoint['lat'], $endPoint['lon']);
    
    if ($distance < 0.5) { // Boucle
        return [
            'type' => 'loop',
            'description' => 'Parcours en boucle - analyse dans les deux sens pertinente',
            'is_loop' => true
        ];
    }
    
    // Parcours linéaire
    $bearing = calculateBearing($startPoint['lat'], $startPoint['lon'], $endPoint['lat'], $endPoint['lon']);
    $direction = bearingToCardinalDirection($bearing);
    
    return [
        'type' => 'linear',
        'description' => "Parcours linéaire vers le $direction",
        'direction' => $direction,
        'bearing' => round($bearing, 1),
        'is_loop' => false
    ];
}

/**
 * Gestion de l'analyse du vent
 */
function handleWindAnalysis(): void {
    $input = json_decode(file_get_contents('php://input'), true);
    
    if (!$input || !isset($input['segments'], $input['datetime'], $input['rider_speed'])) {
        throw new InvalidArgumentException('Données manquantes pour l\'analyse du vent');
    }
    
    $segments = $input['segments'];
    $datetime = $input['datetime'];
    $riderSpeed = (float)$input['rider_speed'];
    
    // Valider la date
    $date = DateTime::createFromFormat('Y-m-d\TH:i', $datetime);
    if (!$date) {
        throw new InvalidArgumentException('Format de date/heure invalide');
    }
    
    $weatherData = fetchWeatherData($segments, $datetime);
    $analysis = analyzeWindImpact($segments, $weatherData, $riderSpeed, $datetime);
    $analysis = analyzeWindImpact($segments, $weatherData, $riderSpeed, $datetime);

    
    respondSuccess($analysis);
}

/**
 * Récupération des données météorologiques
 */
function fetchWeatherData(array $segments, string $datetime): array {
    $centerPoint = calculateRouteCenter($segments);
    
    $startDate = date('Y-m-d', strtotime($datetime . ' -1 day'));
    $endDate = date('Y-m-d', strtotime($datetime . ' +1 day'));
    
    $params = [
        'latitude' => round($centerPoint['lat'], 4),
        'longitude' => round($centerPoint['lon'], 4),
        'hourly' => 'wind_speed_10m,wind_direction_10m,temperature_2m',
        'timezone' => 'Europe/Paris',
        'start_date' => $startDate,
        'end_date' => $endDate
    ];
    
    $url = 'https://api.open-meteo.com/v1/forecast?' . http_build_query($params);
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 15,
        CURLOPT_USERAGENT => 'RideFlow/2.1'
    ]);
    
    $response = curl_exec($ch);
    
    if (curl_errno($ch)) {
        $error = curl_error($ch);
        curl_close($ch);
        throw new RuntimeException('Erreur API Open-Meteo: ' . $error);
    }
    
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($httpCode !== 200) {
        throw new RuntimeException("Erreur API Open-Meteo: HTTP $httpCode");
    }
    
    $data = json_decode($response, true);
    if (!$data || !isset($data['hourly'])) {
        throw new RuntimeException('Données météo invalides');
    }
    
    return $data['hourly'];
}

/**
 * Analyse complète de l'impact du vent avec évolution temporelle
 */
function analyzeWindImpact(array $segments, array $weatherData, float $riderSpeed, string $datetime): array {
    $analyzedSegments = [];
    $summary = initializeSummary();
    $cumulativeTime = 0;
    
    foreach ($segments as $segment) {
        $segmentAnalysis = analyzeSegmentWindEvolutive($segment, $weatherData, $riderSpeed, $datetime, $cumulativeTime);
        $analyzedSegments[] = $segmentAnalysis;
        updateSummary($summary, $segmentAnalysis, $segment);
        
        $cumulativeTime += $segmentAnalysis['base_time_minutes'];
    }
    
    finalizeSummary($summary, count($segments));
    
    return [
        'segments' => $analyzedSegments,
        'center_point' => calculateRouteCenter($segments),
        // CORRECTION: Passer le temps total cumulé
        'dominant_wind' => calculateDominantWindEvolutive($weatherData, $datetime, $cumulativeTime),
        'summary' => $summary
    ];
}

/**
 * Analyse du vent pour un segment avec évolution temporelle
 */
function analyzeSegmentWindEvolutive(array $segment, array $weatherData, float $riderSpeed, string $datetime, float $cumulativeTime): array {
    // Calculer l'heure d'arrivée sur ce segment
    $segmentDateTime = calculateSegmentDateTime($datetime, $cumulativeTime);
    $weatherIndex = findWeatherIndexEvolutive($weatherData, $segmentDateTime);
    
    $windSpeed = $weatherData['wind_speed_10m'][$weatherIndex] ?? 15;
    $windDirection = $weatherData['wind_direction_10m'][$weatherIndex] ?? 180;

    // Impact pour sens normal et inverse
    $impactNormal = calculateWindImpact($segment['bearing'], $windDirection, $windSpeed);
    $impactReverse = calculateWindImpact(($segment['bearing'] + 180) % 360, $windDirection, $windSpeed);
    
    // Calcul des temps
    $baseTime = ($segment['distance'] / $riderSpeed) * 60;
    $timeNormal = $baseTime * (1 + $impactNormal['factor']);
    $timeReverse = $baseTime * (1 + $impactReverse['factor']);
    
    return array_merge($segment, [
        'segment_datetime' => $segmentDateTime,
        'cumulative_time' => round($cumulativeTime, 2),
        'wind_speed' => round($windSpeed, 1),
        'wind_direction' => round($windDirection),
        'wind_direction_text' => bearingToText($windDirection),
        'wind_impact' => $impactNormal['type'],
        'wind_impact_value' => round($impactNormal['factor'], 3),
        'wind_impact_reverse' => $impactReverse['type'],
        'wind_impact_value_reverse' => round($impactReverse['factor'], 3),
        'estimated_time_minutes' => round($timeNormal, 2),
        'estimated_time_reverse_minutes' => round($timeReverse, 2),
        'base_time_minutes' => round($baseTime, 2)
    ]);
}

/**
 * Calcule la date/heure d'arrivée sur un segment
 */
function calculateSegmentDateTime(string $startDateTime, float $cumulativeTimeMinutes): string {
    $timestamp = strtotime($startDateTime);
    if ($timestamp === false) {
        error_log("Date invalide dans calculateSegmentDateTime: $startDateTime");
        return $startDateTime;
    }
    
    // SOLUTION SIMPLE ET PROPRE
    $newTimestamp = $timestamp + (int)round($cumulativeTimeMinutes * 60);
    return date('Y-m-d\TH:i', $newTimestamp);
}

/**
 * Trouve l'index météo le plus proche pour une date/heure donnée
 */
function findWeatherIndexEvolutive(array $weatherData, string $targetDateTime): int {
    if (!isset($weatherData['time']) || empty($weatherData['time'])) {
        // Fallback si pas de données temporelles - utiliser l'heure de la journée
        $hour = (int)date('H', strtotime($targetDateTime));
        $maxIndex = count($weatherData['wind_speed_10m']) - 1;
        return min($hour, $maxIndex);
    }
    
    $targetTimestamp = strtotime($targetDateTime);
    if ($targetTimestamp === false) {
        error_log("Date invalide dans findWeatherIndexEvolutive: $targetDateTime");
        return 0;
    }
    
    $bestIndex = 0;
    $minDiff = PHP_INT_MAX;
    
    foreach ($weatherData['time'] as $index => $timeStr) {
        $weatherTimestamp = strtotime($timeStr);
        if ($weatherTimestamp === false) {
            continue;
        }
        
        $diff = abs($weatherTimestamp - $targetTimestamp);
        
        if ($diff < $minDiff) {
            $minDiff = $diff;
            $bestIndex = $index;
        }
        
        // Si on a trouvé une heure exacte ou très proche (< 30 min), on s'arrête
        if ($diff < 1800) { // 30 minutes
            break;
        }
    }
    
    return $bestIndex;
}

/**
 * Calcul du vent dominant basé sur l'évolution temporelle
 */
function calculateDominantWindEvolutive(array $weatherData, string $startDateTime, float $totalTimeMinutes): array {
    // Calculer le vent moyen sur la durée totale du parcours
    $startIndex = findWeatherIndexEvolutive($weatherData, $startDateTime);
    $endDateTime = calculateSegmentDateTime($startDateTime, $totalTimeMinutes);
    $endIndex = findWeatherIndexEvolutive($weatherData, $endDateTime);
    
    // Assurer qu'on a au moins quelques points de données
    $startIndex = max(0, $startIndex);
    $endIndex = min($endIndex, count($weatherData['wind_speed_10m']) - 1);
    $endIndex = max($startIndex, $endIndex); // Au minimum le point de départ
    
    // Gérer le cas où on n'a qu'un seul point
    if ($startIndex === $endIndex) {
        $speeds = [$weatherData['wind_speed_10m'][$startIndex] ?? 15];
        $directions = [$weatherData['wind_direction_10m'][$startIndex] ?? 180];
    } else {
        $speeds = array_slice($weatherData['wind_speed_10m'], $startIndex, $endIndex - $startIndex + 1);
        $directions = array_slice($weatherData['wind_direction_10m'], $startIndex, $endIndex - $startIndex + 1);
    }
    
    // Filtrer les valeurs nulles
    $speeds = array_filter($speeds, fn($v) => $v !== null);
    $directions = array_filter($directions, fn($v) => $v !== null);
    
    if (empty($speeds) || empty($directions)) {
        // Valeurs par défaut en cas de problème
        $avgSpeed = 15;
        $avgDirection = 180;
    } else {
        $avgSpeed = array_sum($speeds) / count($speeds);
        $avgDirection = array_sum($directions) / count($directions);
    }
    
    error_log(sprintf(
        "Vent dominant: %s à %s, indices %d-%d, direction %.1f° (%s), vitesse %.1f km/h", 
        $startDateTime, $endDateTime, $startIndex, $endIndex, 
        $avgDirection, bearingToText($avgDirection), $avgSpeed
    ));
    
    return [
        'speed' => round($avgSpeed, 1),
        'direction' => round($avgDirection),
        'direction_text' => bearingToText($avgDirection),
        'time_span' => [
            'start' => $startDateTime,
            'end' => $endDateTime,
            'duration_minutes' => round($totalTimeMinutes, 1)
        ]
    ];
}

/**
 * Analyse du vent pour un segment
 */
function analyzeSegmentWind(array $segment, array $weatherData, float $riderSpeed, string $datetime): array {
    $weatherIndex = findWeatherIndex($weatherData, $datetime);
    
    $windSpeed = $weatherData['wind_speed_10m'][$weatherIndex] ?? 15;
    $windDirection = $weatherData['wind_direction_10m'][$weatherIndex] ?? 180;
    

    // à supprimer
    error_log(sprintf("Segment %d: vent vient de %d° (%s), va vers %d°", 
    $segment['id'], 
    $windDirection, 
    bearingToText($windDirection),
    ($windDirection + 180) % 360
    ));


    // Impact pour sens normal et inverse
    $impactNormal = calculateWindImpact($segment['bearing'], $windDirection, $windSpeed);
    $impactReverse = calculateWindImpact(($segment['bearing'] + 180) % 360, $windDirection, $windSpeed);
    
    // Calcul des temps
    $baseTime = ($segment['distance'] / $riderSpeed) * 60;
    $timeNormal = $baseTime * (1 + $impactNormal['factor']);
    $timeReverse = $baseTime * (1 + $impactReverse['factor']);
    
    return array_merge($segment, [
        'wind_speed' => round($windSpeed, 1),
        'wind_direction' => round($windDirection),
        'wind_direction_text' => bearingToText($windDirection),
        'wind_impact' => $impactNormal['type'],
        'wind_impact_value' => round($impactNormal['factor'], 3),
        'wind_impact_reverse' => $impactReverse['type'],
        'wind_impact_value_reverse' => round($impactReverse['factor'], 3),
        'estimated_time_minutes' => round($timeNormal, 2),
        'estimated_time_reverse_minutes' => round($timeReverse, 2),
        'base_time_minutes' => round($baseTime, 2)
    ]);
}

/**
 * Calcul de l'impact du vent sur un segment
 */
function calculateWindImpact(float $segmentBearing, float $windDirection, float $windSpeed): array {
    $relativeBearing = abs($segmentBearing - $windDirection);
    if ($relativeBearing > 180) {
        $relativeBearing = 360 - $relativeBearing;
    }
    
    $baseImpact = min($windSpeed / 20, 0.4); // Max 40%
    $minImpact = 0.05; // Min 5%
    
    if ($relativeBearing <= 30) {
        return ['type' => 'unfavorable', 'factor' => max($baseImpact, $minImpact)];
    } elseif ($relativeBearing <= 60) {
        return ['type' => 'unfavorable', 'factor' => max($baseImpact * 0.7, $minImpact)];
    } elseif ($relativeBearing <= 120) {
        return ['type' => 'crosswind', 'factor' => max($baseImpact * 0.3, $minImpact * 0.5)];
    } elseif ($relativeBearing <= 150) {
        return ['type' => 'favorable', 'factor' => -max($baseImpact * 0.5, $minImpact)];
    } else {
        return ['type' => 'favorable', 'factor' => -max($baseImpact * 0.8, $minImpact * 1.5)];
    }
}

/**
 * Fonctions utilitaires
 */
function calculateDistance(float $lat1, float $lon1, float $lat2, float $lon2): float {
    $R = 6371;
    $dLat = deg2rad($lat2 - $lat1);
    $dLon = deg2rad($lon2 - $lon1);
    $a = sin($dLat/2) ** 2 + cos(deg2rad($lat1)) * cos(deg2rad($lat2)) * sin($dLon/2) ** 2;
    $c = 2 * atan2(sqrt($a), sqrt(1-$a));
    return $R * $c;
}

function calculateBearing(float $lat1, float $lon1, float $lat2, float $lon2): float {
    $lat1 = deg2rad($lat1);
    $lat2 = deg2rad($lat2);
    $dLon = deg2rad($lon2 - $lon1);
    $y = sin($dLon) * cos($lat2);
    $x = cos($lat1) * sin($lat2) - sin($lat1) * cos($lat2) * cos($dLon);
    $bearing = rad2deg(atan2($y, $x));
    return ($bearing + 360) % 360;
}

function bearingToText(float $bearing): string {
    $directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                   'S', 'SSO', 'SO', 'OSO', 'O', 'ONO', 'NO', 'NNO'];
    $index = (int)round($bearing / 22.5) % 16;
    return $directions[$index];
}

function bearingToCardinalDirection(float $bearing): string {
    $directions = [
        'Nord' => [337.5, 22.5],
        'Nord-Est' => [22.5, 67.5],
        'Est' => [67.5, 112.5],
        'Sud-Est' => [112.5, 157.5],
        'Sud' => [157.5, 202.5],
        'Sud-Ouest' => [202.5, 247.5],
        'Ouest' => [247.5, 292.5],
        'Nord-Ouest' => [292.5, 337.5]
    ];
    
    foreach ($directions as $direction => $range) {
        if (($bearing >= $range[0]) || ($bearing < $range[1])) {
            return $direction;
        }
        if (($bearing >= $range[0]) && ($bearing < $range[1])) {
            return $direction;
        }
    }
    
    return 'Nord';
}

function calculateRouteCenter(array $segments): array {
    $totalLat = array_sum(array_column(array_column($segments, 'start'), 'lat'));
    $totalLon = array_sum(array_column(array_column($segments, 'start'), 'lon'));
    
    return [
        'lat' => $totalLat / count($segments),
        'lon' => $totalLon / count($segments)
    ];
}

function calculateDominantWind(array $weatherData): array {
    $speeds = $weatherData['wind_speed_10m'] ?? [10];
    $directions = $weatherData['wind_direction_10m'] ?? [180];
    
    $avgSpeed = array_sum(array_slice($speeds, 0, 6)) / min(6, count($speeds));
    $avgDirection = array_sum(array_slice($directions, 0, 6)) / min(6, count($directions));
    
    return [
        'speed' => round($avgSpeed, 1),
        'direction' => round($avgDirection),
        'direction_text' => bearingToText($avgDirection)
    ];
}

function findWeatherIndex(array $weatherData, string $datetime): int {
    if (!isset($weatherData['time'])) {
        return min((int)date('H'), count($weatherData['wind_speed_10m']) - 1);
    }
    
    $targetTimestamp = strtotime($datetime);
    
    foreach ($weatherData['time'] as $index => $timeStr) {
        if (strtotime($timeStr) >= $targetTimestamp) {
            return $index;
        }
    }
    
    return count($weatherData['wind_speed_10m']) - 1;
}

function initializeSummary(): array {
    return [
        'total_time_normal' => 0,
        'total_time_reverse' => 0,
        'headwind_distance_normal' => 0,
        'headwind_distance_reverse' => 0,
        'favorable_segments_normal' => 0,
        'favorable_segments_reverse' => 0,
        'total_distance' => 0
    ];
}

function updateSummary(array &$summary, array $segmentAnalysis, array $segment): void {
    $summary['total_time_normal'] += $segmentAnalysis['estimated_time_minutes'];
    $summary['total_time_reverse'] += $segmentAnalysis['estimated_time_reverse_minutes'];
    $summary['total_distance'] += $segment['distance'];
    
    if ($segmentAnalysis['wind_impact'] === 'unfavorable') {
        $summary['headwind_distance_normal'] += $segment['distance'];
    } elseif ($segmentAnalysis['wind_impact'] === 'favorable') {
        $summary['favorable_segments_normal']++;
    }
    
    if ($segmentAnalysis['wind_impact_reverse'] === 'unfavorable') {
        $summary['headwind_distance_reverse'] += $segment['distance'];
    } elseif ($segmentAnalysis['wind_impact_reverse'] === 'favorable') {
        $summary['favorable_segments_reverse']++;
    }
}

function finalizeSummary(array &$summary, int $segmentCount = 0): void {
    $summary['best_direction'] = $summary['total_time_normal'] <= $summary['total_time_reverse'] ? 'normal' : 'reverse';
    $summary['time_saved_minutes'] = abs($summary['total_time_normal'] - $summary['total_time_reverse']);
    
    // Arrondir les valeurs
    foreach (['total_time_normal', 'total_time_reverse', 'time_saved_minutes', 'headwind_distance_normal', 'headwind_distance_reverse', 'total_distance'] as $key) {
        $summary[$key] = round($summary[$key], 2);
    }
}

function respondSuccess(array $data): void {
    echo json_encode(['success' => true, 'data' => $data], JSON_UNESCAPED_UNICODE);
    exit;
}

?>