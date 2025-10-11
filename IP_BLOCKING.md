## Block For all, Allow for specific some

```bash
sudo ufw --force reset
sudo ufw default deny outgoing
sudo ufw default deny incoming

# allow DNS (needed for domain names to work)
sudo ufw allow out 53

# allow your specific trusted host
sudo ufw allow out to 10.100.201.91

# allow Kaggle main domain (approx Google IPs)
for ip in $(dig +short kaggle.com storage.googleapis.com kaggleusercontent.com); do
  sudo ufw allow out to $ip
done

sudo ufw enable
sudo ufw status
```


### Allow All Again
```bash
sudo ufw --force reset
sudo ufw default allow outgoing
sudo ufw default allow incoming
sudo ufw disable
```