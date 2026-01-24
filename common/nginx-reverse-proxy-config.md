# Nginx 反向代理配置文档

## 配置概述

本配置将三个本地服务通过nginx的80端口暴露到外网：

1. **第一个服务**：通过 `http://your-server-ip/` 访问，代理到 `localhost:8080`
2. **第二个服务**：通过 `http://your-server-ip/app2` 访问，代理到 `localhost:4000`
3. **第三个服务**：通过 `http://your-server-ip/app3` 访问，代理到 `localhost:8010`

## 配置文件位置

- **配置文件**: `/etc/nginx/sites-available/local-proxy`
- **启用链接**: `/etc/nginx/sites-enabled/local-proxy`

## 当前配置

### 访问方式

- **第一个服务**: `http://your-server-ip/` → 代理到 `http://localhost:8080`
- **第二个服务**: `http://your-server-ip/app2` → 代理到 `http://localhost:4000`
- **第三个服务**: `http://your-server-ip/app3` → 代理到 `http://localhost:8010`

### 重要说明

⚠️ **端口冲突问题**：
- nginx本身监听80端口，所以**不能**代理到 `localhost:80`（会造成循环代理）
- 如果您的第一个服务运行在80端口，需要：
  1. 将服务迁移到其他端口（如3000、8080等）
  2. 然后修改配置文件中的 `proxy_pass` 端口号

## 修改配置

### 如果第一个服务在其他端口

编辑配置文件：

```bash
sudo nano /etc/nginx/sites-available/local-proxy
```

找到这一行：
```nginx
proxy_pass http://localhost:8080;
```

修改为您的服务实际端口，例如：
```nginx
proxy_pass http://localhost:3000;  # 如果服务在3000端口
```

然后测试并重载配置：
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 如果需要去掉路径前缀

如果访问 `http://your-server-ip/app2/api` 时，希望代理到 `http://localhost:4000/api`（而不是 `http://localhost:4000/app2/api`），可以取消注释rewrite规则：

```nginx
location /app2 {
    proxy_pass http://localhost:4000;
    rewrite ^/app2(.*)$ $1 break;  # 取消这行的注释
    # ... 其他配置
}
```

同样，对于 `/app3` 路径，如果需要去掉前缀：

```nginx
location /app3 {
    proxy_pass http://localhost:8010;
    rewrite ^/app3(.*)$ $1 break;  # 取消这行的注释
    # ... 其他配置
}
```

## 配置详情

### 代理设置

配置包含以下代理头设置：
- `X-Real-IP`: 客户端真实IP
- `X-Forwarded-For`: 转发链中的IP地址
- `X-Forwarded-Proto`: 原始协议（http/https）
- `Host`: 原始Host头
- `Upgrade` 和 `Connection`: 支持WebSocket升级

### 超时设置

- `proxy_connect_timeout`: 60秒
- `proxy_send_timeout`: 60秒
- `proxy_read_timeout`: 60秒

### 日志文件

- **访问日志**: `/var/log/nginx/local-proxy-access.log`
- **错误日志**: `/var/log/nginx/local-proxy-error.log`

## 常用命令

### 测试配置
```bash
sudo nginx -t
```

### 重载配置（不中断服务）
```bash
sudo systemctl reload nginx
```

### 重启服务
```bash
sudo systemctl restart nginx
```

### 查看状态
```bash
sudo systemctl status nginx
```

### 查看日志
```bash
# 实时查看访问日志
sudo tail -f /var/log/nginx/local-proxy-access.log

# 实时查看错误日志
sudo tail -f /var/log/nginx/local-proxy-error.log
```

## 防火墙配置

如果使用UFW防火墙，确保允许HTTP流量：

```bash
sudo ufw allow 'Nginx HTTP'
# 或允许所有HTTP/HTTPS
sudo ufw allow 'Nginx Full'
```

## 验证配置

### 检查服务是否运行

```bash
# 检查第一个服务（8080端口）
curl http://localhost:8080

# 检查第二个服务（4000端口）
curl http://localhost:4000

# 检查第三个服务（8010端口）
curl http://localhost:8010
```

### 通过nginx访问

```bash
# 访问第一个服务
curl http://localhost/

# 访问第二个服务
curl http://localhost/app2

# 访问第三个服务
curl http://localhost/app3
```

## 故障排查

### 1. 502 Bad Gateway

可能原因：
- 后端服务未运行
- 后端服务端口不正确
- 防火墙阻止连接

解决方法：
```bash
# 检查后端服务是否运行
sudo ss -tulpn | grep :8080
sudo ss -tulpn | grep :4000
sudo ss -tulpn | grep :8010

# 检查nginx错误日志
sudo tail -f /var/log/nginx/local-proxy-error.log
```

### 2. 404 Not Found

可能原因：
- 路径配置不正确
- 后端服务路径不匹配

解决方法：
- 检查后端服务的实际路径
- 考虑使用 `rewrite` 规则调整路径

### 3. 连接超时

可能原因：
- 后端服务响应慢
- 超时设置过短

解决方法：
- 增加超时时间（在配置文件中修改）
- 检查后端服务性能

## 配置日期

2026年1月15日

## 注意事项

1. 确保后端服务在配置的端口上运行
2. 如果修改配置，记得测试语法并重载nginx
3. 定期检查日志文件以发现潜在问题
4. 生产环境建议配置SSL/TLS证书
