<?php
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) ?: '/';
$file = __DIR__ . $path;
if (str_starts_with($path, '/api')) {
    require __DIR__ . '/api/index.php';
    return true;
}
if ($path === '/' || $path === '') {
    require __DIR__ . '/frontend/index.html';
    return true;
}
if (is_file($file)) {
    return false;
}
foreach (['/css/' => '/frontend/css/', '/js/' => '/frontend/js/'] as $prefix => $target) {
    if (str_starts_with($path, $prefix)) {
        $asset = __DIR__ . $target . substr($path, strlen($prefix));
        if (is_file($asset)) {
            $ext = pathinfo($asset, PATHINFO_EXTENSION);
            if ($ext === 'css') header('Content-Type: text/css; charset=utf-8');
            if ($ext === 'js') header('Content-Type: application/javascript; charset=utf-8');
            readfile($asset);
            return true;
        }
    }
}
http_response_code(404);
echo 'Not found';
return true;
