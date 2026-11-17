FROM nginx:1.27-alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
RUN rm -f /usr/share/nginx/html/index.html
COPY allsafe/ /usr/share/nginx/html/
EXPOSE 80
