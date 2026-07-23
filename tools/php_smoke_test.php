<?php
$base = 'http://127.0.0.1:8765';
$checks = [
  ['/api/health', fn($d)=>($d['ok']??false)&&($d['data']['taxa']??0)===152],
  ['/api/stats', fn($d)=>($d['ok']??false)&&($d['data']['total']??0)===152&&($d['data']['families']??0)===51],
  ['/api/enums', fn($d)=>($d['ok']??false)&&count($d['data']['habit']??[])===11&&count($d['data']['zones']??[])===7],
  ['/api/meta', fn($d)=>($d['ok']??false)],
  ['/api/taxa?limit=5&view=summary', fn($d)=>($d['ok']??false)&&count($d['data']['results']??[])>0],
  ['/api/taxa?q=%D8%A8%D9%84%D9%88%D8%B7&limit=10&view=summary', fn($d)=>($d['ok']??false)&&($d['data']['total']??0)>=1],
  ['/api/auth/config', fn($d)=>($d['ok']??false)],
  ['/api/auth/me', fn($d)=>($d['ok']??false)&&($d['data']['permissions']['can_view']??false)===true],
  ['/api/', fn($d)=>($d['ok']??false)&&($d['data']['runtime']??'')==='PHP'],
];
$pass=0; $fail=0;
foreach ($checks as [$path,$pred]) {
  $raw = @file_get_contents($base.$path);
  $d = json_decode($raw ?: '', true);
  $ok = is_array($d) && $pred($d);
  echo ($ok ? 'OK  ' : 'FAIL ') . "GET $path\n";
  $ok ? $pass++ : $fail++;
}
$headers = @get_headers($base.'/api/taxa/DOES-NOT-EXIST-XYZ');
$ok = is_array($headers) && str_contains($headers[0] ?? '', '404');
echo ($ok ? 'OK  ' : 'FAIL ') . "GET missing taxon 404\n";
$ok ? $pass++ : $fail++;
echo "Result: $pass passed, $fail failed\n";
exit($fail ? 1 : 0);
