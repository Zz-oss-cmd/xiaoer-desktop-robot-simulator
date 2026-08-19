# 虚拟设备配置

TCP 虚拟设备支持通过 JSON 文件管理部署参数，示例见项目根目录的
`config.example.json`。原有的无参数启动方式保持不变。

```bash
python virtual_device.py --config config.example.json
```

`--host` 和 `--port` 可以覆盖配置文件中的对应值：

```bash
python virtual_device.py --config config.example.json --port 9000
```

配置项包括监听地址、端口、链路超时、单次接收缓冲区大小、轮询周期、最大并发
连接数和任务队列容量。程序会在监听端口前完成类型、范围及未知字段校验，错误配置
会立即终止启动，避免故障延迟到客户端接入后才暴露。
