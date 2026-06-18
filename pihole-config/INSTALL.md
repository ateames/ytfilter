## Installation

1. Copy the config file to Pi-hole's dnsmasq directory:

   ```bash
   sudo cp 02-ytfilter-block.conf /etc/dnsmasq.d/
   ```

2. Restart Pi-hole DNS:

   ```bash
   pihole restartdns
   ```

3. Verify it's working:

   ```bash
   dig youtube.com @localhost
   ```

   Should return your Pi's IP, not 0.0.0.0 or Google's servers.

4. Test from another device:

   - Open a browser and go to http://youtube.com
   - You should see the ytfilter block page
   - Click "Go to YouTube Home" — should load your app at youtube.home
