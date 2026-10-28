<?php
// A PHP shop page with a signed-in customer. The page signs the customer's id
// on the server with the secret it shares with Hamilton, so the rep can trust
// who it is talking to. The secret never reaches the browser.

$hamilton = getenv('HAMILTON_URL') ?: 'http://127.0.0.1:8900';
$secret = getenv('HAMILTON_IDENTITY_SECRET');

// Stands in for the shop's own session.
$customerId = 'priya@example.com';
$customerName = 'Priya';
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Your account · Loop Sneakers</title>
</head>
<body>
  <h1>Hello, <?= htmlspecialchars($customerName, ENT_QUOTES) ?></h1>
  <p>Your orders and returns are below. The chat in the corner knows it is you.</p>

  <script src="<?= htmlspecialchars($hamilton, ENT_QUOTES) ?>/widget.js" defer
<?php if ($secret): ?>
    data-hamilton-customer="<?= htmlspecialchars($customerId, ENT_QUOTES) ?>"
    data-hamilton-signature="<?= hash_hmac('sha256', $customerId, $secret) ?>"
<?php endif; ?>
  ></script>
</body>
</html>
