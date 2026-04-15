# Nginx 安装文档

## 安装步骤

### 1. 检查当前状态

首先检查nginx是否已经安装：

```bash
which nginx
nginx -v 2>&1 || echo "nginx not installed"
```

### 2. 安装nginx

在Ubuntu/Debian系统上使用apt包管理器安装：

```bash
sudo apt update && sudo apt install -y nginx
```

安装完成后，nginx会自动启动并设置为开机自启。

### 3. 验证安装

检查nginx版本：

```bash
nginx -v
```

验证配置文件语法：

```bash
sudo nginx -t
```

检查服务状态：

```bash
sudo systemctl status nginx
```

## 安装结果

- **nginx版本**: 1.24.0 (Ubuntu)
- **服务状态**: 正在运行（active (running)）
- **开机自启**: 已启用（enabled）
- **配置文件**: 语法检查通过

## 服务管理命令

### 基本操作

- **启动服务**: `sudo systemctl start nginx`
- **停止服务**: `sudo systemctl stop nginx`
- **重启服务**: `sudo systemctl restart nginx`
- **重载配置**: `sudo systemctl reload nginx`（不中断服务）
- **查看状态**: `sudo systemctl status nginx`
- **禁用开机自启**: `sudo systemctl disable nginx`
- **启用开机自启**: `sudo systemctl enable nginx`

### 配置文件操作

- **测试配置**: `sudo nginx -t`
- **查看版本**: `nginx -v`
- **查看编译信息**: `nginx -V`

## 重要文件位置

### 配置文件

- **主配置文件**: `/etc/nginx/nginx.conf`
- **站点配置目录**: `/etc/nginx/sites-available/`
- **启用的站点**: `/etc/nginx/sites-enabled/`
- **模块配置**: `/etc/nginx/conf.d/`

### 网站文件

- **默认网站根目录**: `/var/www/html/`
- **日志文件**: 
  - 访问日志: `/var/log/nginx/access.log`
  - 错误日志: `/var/log/nginx/error.log`

### 其他

- **PID文件**: `/var/run/nginx.pid`
- **锁文件**: `/var/lock/nginx.lock`

## 防火墙配置

如果使用UFW防火墙，需要允许HTTP和HTTPS流量：

```bash
sudo ufw allow 'Nginx Full'
# 或者分别允许HTTP和HTTPS
sudo ufw allow 'Nginx HTTP'
sudo ufw allow 'Nginx HTTPS'
```

## 常见问题排查

### 检查端口占用

```bash
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443
```

### 查看错误日志

```bash
sudo tail -f /var/log/nginx/error.log
```

### 检查进程

```bash
ps aux | grep nginx
```

## 下一步操作

安装完成后，您可以：

1. 配置虚拟主机（server blocks）
2. 设置SSL/TLS证书
3. 配置反向代理
4. 优化性能参数
5. 设置访问控制

## 安装日期

2026年1月15日

## 系统信息

- **操作系统**: Ubuntu (Linux 6.14.0-1015-aws)
- **包管理器**: apt
- **安装方式**: apt包管理器
