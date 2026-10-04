# Putting the chat on a website

The chat is one script tag. It adds a launcher button and, when opened, loads
the chat panel in an iframe served by your repkit server. The iframe keeps the
panel's styles and scripts apart from the site, so it works the same on a
hand-written page, a PHP site, WordPress, Shopify or a React app.

## 1. Run the server somewhere the site can reach

```bash
repkit serve packs/your-company --host 0.0.0.0 --port 8000 --admin
```

Put it behind HTTPS (a reverse proxy such as Caddy or nginx). The examples
below call it `https://chat.example.com`.

## 2. Add the script

### Any HTML page

```html
<script src="https://chat.example.com/widget.js" defer></script>
```

### PHP

```php
<!-- footer.php -->
<script src="https://chat.example.com/widget.js" defer></script>
```

### WordPress

```php
// functions.php
add_action('wp_enqueue_scripts', function () {
    wp_enqueue_script('repkit', 'https://chat.example.com/widget.js', [], null, [
        'strategy'  => 'defer',
        'in_footer' => true,
    ]);
});
```

### React or Next.js

```tsx
// app/layout.tsx
import Script from 'next/script'

<Script src="https://chat.example.com/widget.js" strategy="lazyOnload" />
```

## 3. Optional: tell the rep who is signed in

If a customer is signed in to your site, the rep can remember them between
conversations. A customer id on its own is a claim anyone could make, so your
server signs it with a secret that the chat server also holds.

On the chat server:

```bash
export REPKIT_IDENTITY_SECRET="a long random string"
```

On your site (PHP shown; any language with HMAC-SHA256 works):

```php
<?php
$userId = $_SESSION['user_id'] ?? null;
$secret = getenv('REPKIT_IDENTITY_SECRET');
?>
<script src="https://chat.example.com/widget.js" defer
<?php if ($userId): ?>
  data-repkit-customer="<?= htmlspecialchars($userId, ENT_QUOTES) ?>"
  data-repkit-signature="<?= hash_hmac('sha256', $userId, $secret) ?>"
<?php endif; ?>
></script>
```

The secret never reaches the browser. An id with a missing or wrong signature
is ignored and the conversation is treated as anonymous.

## Script options

| Attribute | Effect |
|---|---|
| `data-repkit-server` | Server address, if the script is not loaded from it |
| `data-repkit-open="true"` | Open the chat when the page loads |
| `data-repkit-pacing="off"` | Show replies at once, without typing delays |
| `data-repkit-customer`, `data-repkit-signature` | A signed-in customer, as above |

## Driving it from your own code

```js
window.repkit.open()
window.repkit.close()
window.repkit.send("Where is my order?")

window.addEventListener("repkit:turn", (event) => {
  // event.detail.text is what the customer sent
  // event.detail.response.bubbles is what the rep replied
})
```

## Calling the API from another origin

The iframe talks to the chat server directly, so the script tag needs no extra
setup. If your own pages call the API with `fetch`, allow their origin:

```bash
repkit serve packs/your-company --allow-origin https://www.example.com
```
