## Installation

1. **Generate or copy TLS certificates** (e.g. with [mkcert](https://github.com/FiloSottile/mkcert)):

   ```bash
   mkcert youtube.com www.youtube.com m.youtube.com youtube.home
   sudo mkdir -p /etc/ssl/ytfilter
   sudo cp youtube.com+*.pem /etc/ssl/ytfilter/
   sudo cp youtube.com+*-key.pem /etc/ssl/ytfilter/
   ```

   Update the `ssl_certificate` and `ssl_certificate_key` paths in `ytfilter.conf` to match your filenames.

2. **Install the CA on client devices** so browsers trust the certificate (mkcert installs locally; export `rootCA.pem` for phones/tablets).

3. **Move Flask to port 5000** in `.env`:

   ```env
   PORT=5000
   APP_BASE_URL=https://youtube.home
   ```

   Restart ytfilter:

   ```bash
   sudo systemctl restart ytfilter
   ```

4. **Install the nginx site config**:

   ```bash
   sudo cp ytfilter.conf /etc/nginx/sites-available/ytfilter
   sudo ln -s /etc/nginx/sites-available/ytfilter /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

5. **Verify**:

   ```bash
   curl -k https://youtube.home -I
   curl -k https://youtube.com -I   # should 302 to https://youtube.home
   ```

   From a device with the CA trusted, open `https://youtube.home` in a browser.
