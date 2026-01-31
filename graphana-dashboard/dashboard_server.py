#!/usr/bin/env python3
"""
Raspberry Pi Stateless Grafana Dashboard
Fully stateless metrics adapter with in-memory processing and rate calculations.
"""

import json
import logging
import time
import threading
import copy
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StatelessMetricsProcessor:
    """
    Stateless metrics processor with single latest sample and derived metrics.
    No disk I/O, no persistence, in-memory only.
    """
    
    def __init__(self, max_age_seconds: int = 30):
        self.latest_sample: Optional[Dict[str, Any]] = None
        self.last_seen_ts: Optional[float] = None
        self.last_counter_values: Dict[str, float] = {}
        self.last_counter_ts: Optional[float] = None
        self.max_age_seconds = max_age_seconds
        self._lock = threading.Lock()
    
    def update(self, sample: Dict[str, Any]) -> bool:
        """
        Update with new sample. Returns True if accepted, False if rejected.
        Detects if timestamp is not advancing (staleness).
        """
        sample_ts = sample.get('ts')
        if sample_ts is None:
            logger.warning("Sample missing timestamp, rejecting")
            return False
        
        with self._lock:
            # Detect if timestamp is not advancing
            if self.last_seen_ts is not None and sample_ts <= self.last_seen_ts:
                logger.warning(f"Timestamp not advancing: {sample_ts} <= {self.last_seen_ts}")
                return False
            
            # Store previous counter values for rate calculation
            if self.latest_sample is not None:
                self.last_counter_values = {
                    'disk.read_sectors': self.latest_sample.get('disk', {}).get('read_sectors', 0),
                    'disk.write_sectors': self.latest_sample.get('disk', {}).get('write_sectors', 0),
                    'network.rx_bytes': self.latest_sample.get('network', {}).get('rx_bytes', 0),
                    'network.tx_bytes': self.latest_sample.get('network', {}).get('tx_bytes', 0),
                }
                self.last_counter_ts = self.last_seen_ts
            
            # Update latest sample
            self.latest_sample = copy.deepcopy(sample)
            self.last_seen_ts = sample_ts
            
            logger.debug(f"Accepted sample with timestamp {sample_ts}")
            return True
    
    def get_latest_with_derived(self) -> Optional[Dict[str, Any]]:
        """
        Get latest sample with derived rate metrics.
        Returns None if no sample available.
        """
        with self._lock:
            if self.latest_sample is None:
                return None
            
            # Create output with derived metrics
            output = copy.deepcopy(self.latest_sample)
            
            # Calculate rates from counters if we have previous values
            if self.last_counter_ts is not None and self.last_seen_ts is not None:
                time_delta = self.last_seen_ts - self.last_counter_ts
                if time_delta > 0:
                    # Disk rates
                    if 'disk' not in output:
                        output['disk'] = {}
                    current_read = output.get('disk', {}).get('read_sectors', 0)
                    current_write = output.get('disk', {}).get('write_sectors', 0)
                    prev_read = self.last_counter_values.get('disk.read_sectors', 0)
                    prev_write = self.last_counter_values.get('disk.write_sectors', 0)
                    
                    output['disk']['read_sectors_rate'] = (current_read - prev_read) / time_delta
                    output['disk']['write_sectors_rate'] = (current_write - prev_write) / time_delta
                    
                    # Network rates
                    if 'network' not in output:
                        output['network'] = {}
                    current_rx = output.get('network', {}).get('rx_bytes', 0)
                    current_tx = output.get('network', {}).get('tx_bytes', 0)
                    prev_rx = self.last_counter_values.get('network.rx_bytes', 0)
                    prev_tx = self.last_counter_values.get('network.tx_bytes', 0)
                    
                    output['network']['rx_bytes_rate'] = (current_rx - prev_rx) / time_delta
                    output['network']['tx_bytes_rate'] = (current_tx - prev_tx) / time_delta
                else:
                    # Zero rates if time delta is invalid
                    if 'disk' not in output:
                        output['disk'] = {}
                    output['disk']['read_sectors_rate'] = 0.0
                    output['disk']['write_sectors_rate'] = 0.0
                    if 'network' not in output:
                        output['network'] = {}
                    output['network']['rx_bytes_rate'] = 0.0
                    output['network']['tx_bytes_rate'] = 0.0
            else:
                # First sample or no previous data - zero rates
                if 'disk' not in output:
                    output['disk'] = {}
                output['disk']['read_sectors_rate'] = 0.0
                output['disk']['write_sectors_rate'] = 0.0
                if 'network' not in output:
                    output['network'] = {}
                output['network']['rx_bytes_rate'] = 0.0
                output['network']['tx_bytes_rate'] = 0.0
            
            return output
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status based on staleness detection.
        Returns: {"status": "ok" | "stale", "last_seen_ts": float | null}
        """
        with self._lock:
            if self.last_seen_ts is None:
                return {"status": "stale", "last_seen_ts": None}
            
            current_time = time.time()
            age_seconds = current_time - self.last_seen_ts
            
            if age_seconds > self.max_age_seconds:
                return {"status": "stale", "last_seen_ts": self.last_seen_ts}
            else:
                return {"status": "ok", "last_seen_ts": self.last_seen_ts}


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for metrics and health endpoints."""
    
    def __init__(self, *args, processor: StatelessMetricsProcessor = None, **kwargs):
        self.processor = processor
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        path = urlparse(self.path).path
        
        if path == '/' or path == '/index.html':
            self._serve_dashboard()
        elif path == '/metrics':
            self._serve_metrics()
        elif path == '/health':
            self._serve_health()
        else:
            self.send_error(404)
    
    def _serve_dashboard(self):
        """Serve HTML dashboard."""
        html = self._get_html()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def _serve_metrics(self):
        """Serve latest sample with derived metrics as JSON object."""
        sample = self.processor.get_latest_with_derived()
        if sample is None:
            self.send_error(503, "No metrics available")
            return
        
        try:
            data = json.dumps(sample).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            logger.error(f"Error serving metrics: {e}")
            self.send_error(500)
    
    def _serve_health(self):
        """Serve health status."""
        health = self.processor.get_health_status()
        try:
            data = json.dumps(health).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            logger.error(f"Error serving health: {e}")
            self.send_error(500)
    
    def _get_html(self) -> str:
        """Generate dashboard HTML with gray background and light colored graphs."""
        return '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Raspberry Pi Metrics Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            background:#808080;
            padding:20px;
            min-height:100vh
        }
        .container{max-width:1400px;margin:0 auto}
        header{
            background:rgba(255,255,255,0.95);
            padding:20px;
            border-radius:10px;
            margin-bottom:20px;
            box-shadow:0 4px 6px rgba(0,0,0,0.1)
        }
        h1{color:#333;margin-bottom:10px}
        .status{
            display:inline-block;
            padding:5px 15px;
            border-radius:20px;
            font-size:14px;
            font-weight:bold;
            margin-left:10px
        }
        .status.ok{background:#10b981;color:white}
        .status.stale{background:#f59e0b;color:white}
        .grid{
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
            gap:20px;
            margin-bottom:20px
        }
        .card{
            background:rgba(255,255,255,0.95);
            padding:20px;
            border-radius:10px;
            box-shadow:0 4px 6px rgba(0,0,0,0.1)
        }
        .card h2{color:#333;margin-bottom:15px;font-size:18px}
        .metric{
            display:flex;
            justify-content:space-between;
            align-items:center;
            padding:10px 0;
            border-bottom:1px solid #e5e7eb
        }
        .metric:last-child{border-bottom:none}
        .metric-label{font-weight:500;color:#6b7280}
        .metric-value{font-size:24px;font-weight:bold;color:#1f2937}
        .metric-unit{font-size:14px;color:#6b7280;margin-left:5px}
        .chart-container{position:relative;height:300px;margin-top:20px}
        .full-width{grid-column:1/-1}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Raspberry Pi Metrics Dashboard <span id="status" class="status stale">Stale</span></h1>
            <p id="lastUpdate">Waiting for data...</p>
        </header>
        <div class="grid">
            <div class="card">
                <h2>CPU Usage %</h2>
                <div class="metric">
                    <span class="metric-label">Usage</span>
                    <span class="metric-value" id="cpuUsage">0<span class="metric-unit">%</span></span>
                </div>
                <div class="chart-container">
                    <canvas id="cpuUsageChart"></canvas>
                </div>
            </div>
            <div class="card">
                <h2>CPU Load (1m)</h2>
                <div class="metric">
                    <span class="metric-label">Load</span>
                    <span class="metric-value" id="cpuLoad">0</span>
                </div>
                <div class="chart-container">
                    <canvas id="cpuLoadChart"></canvas>
                </div>
            </div>
            <div class="card">
                <h2>Available Memory</h2>
                <div class="metric">
                    <span class="metric-label">Available</span>
                    <span class="metric-value" id="memAvailable">0<span class="metric-unit">MB</span></span>
                </div>
                <div class="chart-container">
                    <canvas id="memChart"></canvas>
                </div>
            </div>
            <div class="card">
                <h2>CPU Temperature</h2>
                <div class="metric">
                    <span class="metric-label">Temperature</span>
                    <span class="metric-value" id="cpuTemp">0<span class="metric-unit">°C</span></span>
                </div>
                <div class="chart-container">
                    <canvas id="tempChart"></canvas>
                </div>
            </div>
            <div class="card full-width">
                <h2>Disk Read / Write Rate</h2>
                <div class="chart-container">
                    <canvas id="diskChart"></canvas>
                </div>
            </div>
            <div class="card full-width">
                <h2>Network RX / TX</h2>
                <div class="chart-container">
                    <canvas id="netChart"></canvas>
                </div>
            </div>
        </div>
    </div>
    <script>
        const ENDPOINT='/metrics';
        const HEALTH_ENDPOINT='/health';
        const POLL_INTERVAL=15000;
        
        // Light colored chart options with gray background
        const chartOptions={
            responsive:true,
            maintainAspectRatio:false,
            plugins:{
                legend:{display:true,position:'bottom',labels:{color:'#333'}}
            },
            scales:{
                x:{display:true,grid:{color:'rgba(0,0,0,0.1)'},ticks:{color:'#666'}},
                y:{display:true,beginAtZero:true,grid:{color:'rgba(0,0,0,0.1)'},ticks:{color:'#666'}}
            },
            backgroundColor:'rgba(255,255,255,0.8)'
        };
        
        // Light colored datasets
        const lightColors={
            primary:'#87CEEB',
            secondary:'#98D8C8',
            accent:'#F7DC6F',
            warning:'#F8B739',
            info:'#85C1E2',
            success:'#82E0AA'
        };
        
        const cpuUsageChart=new Chart(document.getElementById('cpuUsageChart'),{
            type:'line',
            data:{labels:[],datasets:[{label:'CPU Usage %',data:[],borderColor:lightColors.primary,backgroundColor:lightColors.primary+'40',fill:true}]},
            options:chartOptions
        });
        
        const cpuLoadChart=new Chart(document.getElementById('cpuLoadChart'),{
            type:'line',
            data:{labels:[],datasets:[{label:'CPU Load (1m)',data:[],borderColor:lightColors.secondary,backgroundColor:lightColors.secondary+'40',fill:true}]},
            options:chartOptions
        });
        
        const memChart=new Chart(document.getElementById('memChart'),{
            type:'line',
            data:{labels:[],datasets:[{label:'Available Memory (MB)',data:[],borderColor:lightColors.info,backgroundColor:lightColors.info+'40',fill:true}]},
            options:chartOptions
        });
        
        const tempChart=new Chart(document.getElementById('tempChart'),{
            type:'line',
            data:{labels:[],datasets:[{label:'CPU Temperature (°C)',data:[],borderColor:lightColors.warning,backgroundColor:lightColors.warning+'40',fill:true}]},
            options:chartOptions
        });
        
        const diskChart=new Chart(document.getElementById('diskChart'),{
            type:'line',
            data:{labels:[],datasets:[
                {label:'Read Rate',data:[],borderColor:lightColors.primary,backgroundColor:lightColors.primary+'40',fill:true},
                {label:'Write Rate',data:[],borderColor:lightColors.secondary,backgroundColor:lightColors.secondary+'40',fill:true}
            ]},
            options:chartOptions
        });
        
        const netChart=new Chart(document.getElementById('netChart'),{
            type:'line',
            data:{labels:[],datasets:[
                {label:'RX Rate',data:[],borderColor:lightColors.info,backgroundColor:lightColors.info+'40',fill:true},
                {label:'TX Rate',data:[],borderColor:lightColors.accent,backgroundColor:lightColors.accent+'40',fill:true}
            ]},
            options:chartOptions
        });
        
        const charts=[cpuUsageChart,cpuLoadChart,memChart,tempChart,diskChart,netChart];
        
        function fmt(n){return new Intl.NumberFormat().format(n)}
        function fmtB(b){
            if(b===0)return'0 B';
            const k=1024,s=['B','KB','MB','GB'],i=Math.floor(Math.log(b)/Math.log(k));
            return Math.round(b/Math.pow(k,i)*100)/100+' '+s[i]
        }
        
        function updateMetrics(data){
            const t=new Date(data.ts*1000);
            const timeLabel=t.toLocaleTimeString();
            
            // Update status
            fetch(HEALTH_ENDPOINT).then(r=>r.json()).then(health=>{
                const statusEl=document.getElementById('status');
                statusEl.textContent=health.status==='ok'?'OK':'Stale';
                statusEl.className='status '+health.status;
            }).catch(()=>{});
            
            document.getElementById('lastUpdate').textContent='Last update: '+t.toLocaleString();
            
            // CPU Usage %
            const cpuUsage=data.cpu?.usage_percent||0;
            document.getElementById('cpuUsage').innerHTML=cpuUsage.toFixed(1)+'<span class="metric-unit">%</span>';
            updateChart(cpuUsageChart,cpuUsage,timeLabel);
            
            // CPU Load (1m)
            const cpuLoad=data.cpu?.load_1m||0;
            document.getElementById('cpuLoad').textContent=cpuLoad.toFixed(2);
            updateChart(cpuLoadChart,cpuLoad,timeLabel);
            
            // Available Memory
            const memAvail=data.memory?.available_mb||0;
            document.getElementById('memAvailable').innerHTML=fmt(memAvail)+'<span class="metric-unit">MB</span>';
            updateChart(memChart,memAvail,timeLabel);
            
            // CPU Temperature
            const temp=data.thermal?.cpu_temp_c||0;
            document.getElementById('cpuTemp').innerHTML=temp.toFixed(1)+'<span class="metric-unit">°C</span>';
            updateChart(tempChart,temp,timeLabel);
            
            // Disk Read/Write Rate
            const diskReadRate=data.disk?.read_sectors_rate||0;
            const diskWriteRate=data.disk?.write_sectors_rate||0;
            updateChart(diskChart,[diskReadRate,diskWriteRate],timeLabel,true);
            
            // Network RX/TX Rate
            const netRxRate=data.network?.rx_bytes_rate||0;
            const netTxRate=data.network?.tx_bytes_rate||0;
            updateChart(netChart,[netRxRate,netTxRate],timeLabel,true);
        }
        
        function updateChart(chart,value,label,multi=false){
            chart.data.labels.push(label);
            if(multi&&Array.isArray(value)){
                value.forEach((v,i)=>chart.data.datasets[i].data.push(v));
            }else{
                chart.data.datasets[0].data.push(value);
            }
            if(chart.data.labels.length>20){
                chart.data.labels.shift();
                chart.data.datasets.forEach(d=>d.data.shift());
            }
            chart.update('none');
        }
        
        async function fetchMetrics(){
            try{
                const r=await fetch(ENDPOINT);
                if(r.ok){
                    const d=await r.json();
                    if(d&&typeof d==='object'&&'ts' in d){
                        updateMetrics(d);
                    }
                }
            }catch(e){
                console.error('Failed to fetch metrics:',e);
                document.getElementById('status').textContent='Stale';
                document.getElementById('status').className='status stale';
            }
        }
        
        fetchMetrics();
        setInterval(fetchMetrics,POLL_INTERVAL);
    </script>
</body>
</html>'''
    
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")


def _fetch_metrics_sync(endpoint: str, timeout: int) -> Optional[Dict[str, Any]]:
    """Synchronous HTTP fetch for metrics."""
    try:
        req = Request(endpoint)
        with urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = resp.read()
                return json.loads(data.decode('utf-8'))
            else:
                logger.warning(f"Upstream returned status {resp.status}")
                return None
    except URLError as e:
        logger.warning(f"Failed to fetch metrics: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching metrics: {e}")
        return None


def poll_upstream_metrics(endpoint: str, processor: StatelessMetricsProcessor, 
                          poll_interval: int = 15, timeout: int = 2):
    """Poll upstream metrics endpoint and update processor."""
    logger.info(f"Starting polling loop: {endpoint} (interval: {poll_interval}s)")
    while True:
        try:
            metrics_data = _fetch_metrics_sync(endpoint, timeout)
            
            if metrics_data is not None:
                try:
                    # Handle both array and single object responses
                    if isinstance(metrics_data, list):
                        if len(metrics_data) > 0:
                            # Find the sample with the newest timestamp (not just the last one)
                            newest_sample = max(metrics_data, key=lambda x: x.get('ts', 0) if isinstance(x, dict) else 0)
                            sample_ts = newest_sample.get('ts')
                            if processor.update(newest_sample):
                                logger.info(f"Accepted new sample with timestamp {sample_ts}")
                            else:
                                logger.debug(f"Rejected sample with timestamp {sample_ts} (not advancing)")
                        else:
                            logger.warning("Empty metrics array received")
                    elif isinstance(metrics_data, dict):
                        # Single object response
                        sample_ts = metrics_data.get('ts')
                        if processor.update(metrics_data):
                            logger.info(f"Accepted new sample with timestamp {sample_ts}")
                        else:
                            logger.debug(f"Rejected sample with timestamp {sample_ts} (not advancing)")
                    else:
                        logger.warning(f"Unexpected metrics format: {type(metrics_data)}")
                except Exception as e:
                    logger.error(f"Error processing metrics: {e}")
            else:
                logger.debug("No metrics data received from upstream")
            
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Polling loop interrupted")
            break
        except Exception as e:
            logger.error(f"Error in polling loop: {e}")
            time.sleep(poll_interval)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Raspberry Pi Stateless Grafana Dashboard')
    parser.add_argument('--port', type=int, default=9100, help='Port (default: 9100)')
    parser.add_argument('--bind', type=str, default='0.0.0.0', help='Bind address (default: 0.0.0.0)')
    parser.add_argument('--metrics-endpoint', type=str, 
                       default='http://100.67.229.89:9000/latest', 
                       help='Upstream metrics URL')
    parser.add_argument('--poll-interval', type=int, default=15, 
                       help='Poll interval in seconds (default: 15)')
    parser.add_argument('--timeout', type=int, default=10, 
                       help='Request timeout in seconds (default: 10)')
    parser.add_argument('--max-age', type=int, default=30, 
                       help='Max age in seconds for staleness detection (default: 30)')
    
    args = parser.parse_args()
    
    # Create processor
    processor = StatelessMetricsProcessor(max_age_seconds=args.max_age)
    
    # Start polling thread (minimal background thread for polling)
    polling_thread = threading.Thread(
        target=poll_upstream_metrics,
        args=(args.metrics_endpoint, processor, args.poll_interval, args.timeout),
        daemon=True
    )
    polling_thread.start()
    logger.info(f"Started polling thread for: {args.metrics_endpoint}")
    
    def handler(*a, **kw):
        return DashboardHandler(*a, processor=processor, **kw)
    
    server = HTTPServer((args.bind, args.port), handler)
    logger.info(f"Dashboard server: http://{args.bind}:{args.port}")
    logger.info(f"Metrics endpoint: http://{args.bind}:{args.port}/metrics")
    logger.info(f"Health endpoint: http://{args.bind}:{args.port}/health")
    logger.info(f"Upstream metrics: {args.metrics_endpoint}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
