import socket
import struct
import numpy as np
from PyQt5 import QtWidgets
import pyqtgraph as pg
import sys

class EEGVisualizer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live EEG Visualizer")
        self.resize(1200, 600)

        self.plot_widget = pg.GraphicsLayoutWidget()
        self.setCentralWidget(self.plot_widget)

        self.num_channels = 8
        self.plots = []
        self.curves = []

        # For marker tracking
        self.markers = []  # list of dicts: { 'x': int, 'lines': [...], 'label': TextItem }

        for i in range(self.num_channels):
            p = self.plot_widget.addPlot(row=i, col=0)
            p.setYRange(-1000, 1000)
            p.showGrid(x=True, y=True)
            p.setLabel('left', f'Ch {i+1}', units='µV')
            curve = p.plot(pen=pg.mkPen('g', width=1.5))
            self.plots.append(p)
            self.curves.append(curve)
        
        self.buffer = np.zeros((self.num_channels, 10000))  # 1 second buffer at 500 Hz
        # Set time labels on the x-axis (assuming 500 Hz)
        tick_spacing = 500  # 500 samples = 1 second
        time_ticks = [(i, f"{i//500}s") for i in range(0, self.buffer.shape[1]+1, tick_spacing)]

        for plot in self.plots:
            plot.getAxis('bottom').setTicks([time_ticks])



        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(20)  # Update every 20 ms

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(("127.0.0.1", 50000))
        self.socket.setblocking(False)

    def update_plot(self):
        try:
            header_size = 24
            header = self.socket.recv(header_size, socket.MSG_PEEK)
            if len(header) < header_size:
                return

            guid1, guid2, guid3, guid4, msgsize, msgtype = struct.unpack('<llllLL', header)
            if msgtype != 4:
                self.socket.recv(msgsize)
                return

            data = b''
            while len(data) < msgsize:
                chunk = self.socket.recv(msgsize - len(data))
                if not chunk:
                    return
                data += chunk

            payload = data[24:]
            block_id, num_samples, num_markers = struct.unpack('<LLL', payload[:12])

            eeg_data_bytes = self.num_channels * num_samples * 4
            flat_data = np.frombuffer(payload[12:12 + eeg_data_bytes], dtype=np.float32).copy()
            eeg_matrix = flat_data.reshape((self.num_channels, num_samples))
            # eeg_matrix /= 1e6

            # Scroll buffer
            self.buffer = np.roll(self.buffer, -num_samples, axis=1)
            self.buffer[:, -num_samples:] = eeg_matrix

            # Update curves
            for i in range(self.num_channels):
                self.curves[i].setData(self.buffer[i])
            
            

            # Shift marker positions and update their graphics
            for marker in self.markers:
                marker['x'] -= num_samples
                for i, line in enumerate(marker['lines']):
                    line.setValue(marker['x'])
                marker['label'].setPos(marker['x'], 0)

            # Remove markers that are out of view
            for marker in self.markers[:]:
                if marker['x'] < 0:
                    for i in range(self.num_channels):
                        self.plots[i].removeItem(marker['lines'][i])
                    self.plots[0].removeItem(marker['label'])  # Remove label from first plot only
                    self.markers.remove(marker)

            # Parse and add new markers
            marker_ptr = 12 + eeg_data_bytes
            for _ in range(num_markers):
                if marker_ptr + 4 > len(payload):
                    break
                marker_size = struct.unpack('<L', payload[marker_ptr:marker_ptr+4])[0]
                marker_ptr += 4

                position, points, channel = struct.unpack('<LLl', payload[marker_ptr:marker_ptr+12])
                marker_ptr += 12

                # type (null-terminated)
                type_bytes = b''
                while payload[marker_ptr:marker_ptr+1] != b'\x00':
                    type_bytes += payload[marker_ptr:marker_ptr+1]
                    marker_ptr += 1
                marker_ptr += 1

                # description (null-terminated)
                desc_bytes = b''
                while payload[marker_ptr:marker_ptr+1] != b'\x00':
                    desc_bytes += payload[marker_ptr:marker_ptr+1]
                    marker_ptr += 1
                marker_ptr += 1

                description = desc_bytes.decode('utf-8')
                xpos = self.buffer.shape[1] - num_samples + position

                lines = []
                for i in range(self.num_channels):
                    vline = pg.InfiniteLine(pos=xpos, angle=90, pen=pg.mkPen('r', width=1))
                    self.plots[i].addItem(vline)
                    lines.append(vline)

                label = pg.TextItem(text=description, color='r', anchor=(0, 1))
                label.setPos(xpos, 0)
                self.plots[0].addItem(label)

                self.markers.append({'x': xpos, 'lines': lines, 'label': label})

        except BlockingIOError:
            pass

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = EEGVisualizer()
    win.show()
    sys.exit(app.exec_())
