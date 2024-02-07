sudo pip3 install -r requirements.txt
sudo cp kardi.ini /etc/uwsgi/apps/
sudo cp agents_kardiru.conf /etc/supervisor/conf.d/
sudo cp agents_kardiru_nginx.conf /etc/nginx/sites-enabled/
sudo supervisorctl update
sudo systemctl restart nginx
sudo certbot --nginx -d kardiru.medsenger.ru
