import sys
import os
from threading import Thread
from multiprocessing import Process, Queue, Event
from pathlib import Path
import cv2
import torch
import torch.backends.cudnn as cudnn
from multiprocessing import Queue
from models.common import DetectMultiBackend
from utils.dataloaders import LoadStreams
from utils.general import (
    check_img_size, non_max_suppression, scale_boxes)
from utils.plots import Annotator, colors, save_one_box
from utils.torch_utils import select_device, time_sync
from utils.logger import getLogger
from tkinter import Tk, Label
from PIL import Image, ImageTk
from firebase import TempDb
from firebase_admin.db import Event as dbEvent
from deepdiff import DeepDiff
from datetime import datetime
from utils.datetimefunc import datetime_now, seconds_from_now
import easyocr
from operator import contains
from constants.license_plate import LICENSE_NUMBER_CHARS
from config import MODEL_NAME

# > Initialize project path
FILE = Path(__file__).resolve()
ROOT = FILE.parents[0]  # ROOT Directory
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # add ROOT to PATH
ROOT = Path(os.path.relpath(ROOT, Path.cwd()))  # Relative path


def inference(
    name: str,  # name
    source: str,  # Path to the source. (Default: Webcam (0))
    queue: Queue,  # Share memory between process and
    stop_event: Event,
):
    # > Get logger and setting the logging level.
    logger = getLogger(f'{name.title()}')
    logger.propagate = False
    logger.info("YOLOv5 initializing.")

    # > Initialze YOLOv5 settings.
    source = str(source)
    # Detection model path.
    weights = ROOT / f'models/{MODEL_NAME}'
    data = ROOT / 'data/coco128.yaml'  # Dataset path.
    imgsz = (640, 640)  # Inference size. (height, width)
    conf_thres = 0.25  # Confidence threshold.
    iou_thres = 0.45  # NMS IOU threshold.
    max_det = 1000  # Maximum detections per image.
    device = ''  # Cuda device, i.e. 0 or 0,1,2,3 or cpu.
    classes = None  # Filter by class: --class 0, or --class 0 2 3.
    agnostic_nms = False  # Class-agnostic NMS.
    augment = False  # Augmented inference.
    line_thickness = 2  # Bounding box thickness (pixels).
    half = False  # Use FP16 half-precisiob inference.
    dnn = False  # Use OpenCV DNN for ONNX inference.

    # > Initialize EasyOCR reader.
    logger.info("EasyOCR initializing.")
    reader = easyocr.Reader(['th'])

    # GUI settings
    logger.info("Preview GUI initializing.")
    gui = Tk()
    gui.title(f'ALPR: {name.capitalize()} Preview')
    gui.geometry("800x750+20+0" if name != 'exit' else "800x750+850+0")
    gui.minsize("800", "750")
    gui.maxsize("800", "750")
    gui.rowconfigure(0, minsize="450")
    gui.rowconfigure(2, minsize="225")

    # Widgets

    # video_feed
    video_feed = Label(gui, text="(source video)")
    video_feed.grid(row=0, column=0, columnspan=2)
    video_feed_label = Label(gui, text="Video Feed")
    video_feed_label.grid(row=1, column=0,  columnspan=3, pady=(5, 5))

    # input_feed
    input_feed = Label(gui, text="(wait for license plate detection)")
    input_feed.grid(row=2, column=0)
    input_feed_label = Label(gui, text="ALPR: Histogram Equalized")
    input_feed_label.grid(row=3, column=0, pady=(5, 5))

    # OCR feed.
    ocr_feed = Label(gui, text="(wait for license plate detection)")
    ocr_feed.grid(row=2, column=1)
    ocr_feed_label = Label(gui, text="ALPR: OCR")
    ocr_feed_label.grid(row=3, column=1, pady=(5, 5))

    # Step 1: Loading model.
    device = select_device(device)
    model = DetectMultiBackend(
        weights, device=device, dnn=dnn, data=data, fp16=half)
    stride, names, pt = model.stride, model.names, model.pt
    imgsz = check_img_size(imgsz=imgsz, s=stride)

    # Step 2: Loading source.
    cudnn.benchmark = True  # set True to speed up constant image size inference
    dataset = LoadStreams(source, img_size=imgsz, stride=stride, auto=pt)
    bs = len(dataset)  # batch_size

    # Step 3: Run inference.
    model.warmup(imgsz=(1 if pt else bs, 3, *imgsz))  # warm up
    seen, dt = 0, [0.0, 0.0, 0.0]
    for path, im, im0s, vid_cap, s in dataset:
        t1 = time_sync()
        im = torch.from_numpy(im).to(device)
        im = im.half() if model.fp16 else im.float()  # uint8 to fp16/32
        im /= 255  # 0 - 255 to 0.0 - 1.0
        if len(im.shape) == 3:
            im = im[None]  # expand for batch dim
        t2 = time_sync()
        dt[0] += t2 - t1

        # Inference
        pred = model(im, augment=augment, visualize=False)
        t3 = time_sync()
        dt[1] += t3 - t2

        # NMS
        pred = non_max_suppression(
            pred, conf_thres, iou_thres, classes, agnostic_nms, max_det=max_det)
        dt[2] += time_sync() - t3

        # Process predictions
        for i, det in enumerate(pred):  # per image
            seen += 1

            # Step 3.1: Setup predicted image and annotator.
            p, im0, frame = path[i], im0s[i].copy(), dataset.count
            s += '%gx%g ' % im.shape[2:]  # print string
            annotator = Annotator(
                im0, line_width=line_thickness, example=str(names))
            imc = im0.copy()

            iminput, imocr = None, None
            license_number = ''

            video_feed_label.configure(
                text=f"No license plate detected.", background="red")
            if len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_boxes(
                    im.shape[2:], det[:, :4], im0.shape).round()

                # Print results
                for c in det[:, -1].unique():
                    n = (det[:, -1] == c).sum()  # detection per class
                    # add to string
                    s += f"{n} {names[int(c)]}{'s' * (n > 1)}"

                # Write results
                # Step 3.2: Crop detected sections in images
                imcs = []
                for *xyxy, conf, cls in reversed(det):
                    c = int(cls)  # integer class
                    label = None
                    annotator.box_label(xyxy, label, color=colors(c, True))
                    imcs.append(save_one_box(
                        xyxy, imc, BGR=True, save=False))

                # Step 3.3: Find biggest crop section.
                iminput = None
                maxArea = 0
                for imc in imcs:
                    area = imc.shape[0] * imc.shape[1]
                    if area > maxArea:
                        iminput = imc

                # Step 3.4: Apply OCR.
                iminput = cv2.equalizeHist(
                    cv2.cvtColor(iminput, cv2.COLOR_BGR2GRAY))
                ocr_outputs = reader.readtext(
                    iminput, add_margin=0.3, width_ths=0.9)
                imocr = iminput.copy()
                texts = []
                boxes = []
                # filter out output with less than 60% confidence.
                for (bbox, text, prob) in ocr_outputs:
                    if prob > 0.1:
                        texts.append(text)
                        boxes.append({'bbox': bbox, 'chosen': False})

                # Step 3.5: Check pattern license number pattern.
                filtered_texts = []  # limit 2 texts
                for i, text in enumerate(texts):  # ignore province.
                    # if reach limit filtered texts. -> break loop.
                    if len(filtered_texts) >= 2:
                        break
                    # if text more than 10 characters or less than 2 -> ignore text.
                    elif len(text) > 10 or len(text) < 2:
                        continue
                    else:
                        is_contain_number = False
                        for char in text:  # check is text contain number.
                            if char.isdigit():
                                is_contain_number = True
                                break
                        # append when contain number or has 2 characters.
                        if is_contain_number or len(text) <= 2:
                            filtered_texts.append(text)
                            boxes[i].update({'chosen': True})
                for box in boxes:  # draw box on ocr image.
                    (tl, tr, br, bl) = box.get('bbox', None)
                    chosen = box.get('chosen', None)
                    tl = (int(tl[0]), int(tl[1]))
                    tr = (int(tr[0]), int(tr[1]))
                    br = (int(br[0]), int(br[1]))
                    bl = (int(bl[0]), int(bl[1]))
                    cv2.rectangle(imocr, tl, br, (0, 255, 0)
                                  if chosen else (0, 0, 255), 2)

                filtered_text = ''
                # re-order texts if has more than one text.
                if len(filtered_texts) == 2:
                    i_0_front = len(filtered_texts[0]) < 4
                    filtered_text = f'{filtered_texts[0]}{filtered_texts[1]}' if i_0_front else f'{filtered_texts[1]}{filtered_texts[0]}'
                if len(filtered_texts) == 1:  # assign to filtered_text.
                    filtered_text = filtered_texts[0]
                is_contain_digit = False
                for char in filtered_text:  # check is filtered_text contains number.
                    if char.isdigit():
                        is_contain_digit = True
                        break
                if is_contain_digit:
                    for char in filtered_text:
                        if contains(LICENSE_NUMBER_CHARS, char):
                            license_number += char

                # Step 3.6: Update node values.
                if len(license_number) > 0:
                    queue.put(license_number)
                    video_feed_label.configure(
                        text=f"License plate detected. License number: {license_number}", background="green")
                    s += f' License ID found. ({license_number}) '
                else:
                    video_feed_label.configure(
                        text=f"License plate detected. No license number detected.", background="orange")
                    s += f' License ID not found. '

            # Stream results
            im0 = annotator.result()
            img_im0 = Image.fromarray(cv2.cvtColor(im0, cv2.COLOR_BGR2RGB)).resize(
                (800, 450), Image.ANTIALIAS)
            imgtk_im0 = ImageTk.PhotoImage(img_im0)
            video_feed.configure(image=imgtk_im0)
            if iminput is not None:
                img_iminput = Image.fromarray(iminput).resize(
                    (400, 225), Image.ANTIALIAS)
                imgtk_iminput = ImageTk.PhotoImage(img_iminput)
                input_feed.configure(image=imgtk_iminput)
            if imocr is not None:
                img_imcontour = Image.fromarray(imocr).resize(
                    (400, 225), Image.ANTIALIAS)
                imgtk_imcontour = ImageTk.PhotoImage(img_imcontour)
                ocr_feed.configure(image=imgtk_imcontour)

            gui.update_idletasks()
            gui.update()

        # Print time (inference-only)
        # logger.info(f'{s} Done. ({t3 - t2:.3f}s)')

        # Check is stop event is set.
        if stop_event.is_set():
            break

    # Print results
    t = tuple(x / seen * 1E3 for x in dt)  # speeds per image
    logger.info(
        f'Speed: %.1fms pre-process, %.1fms inference, %.1fms NMS per image at shape {(1, 3, *imgsz)}' % t)


class ALPR:
    def __init__(
        self,
        name='node',  # node name.
        source: str = '0',  # source path. (Default: Webcam (0))
    ):
        # > Local variables
        self.name = name
        logger_name = f'{name.title()}'
        self._logger = getLogger(logger_name)

        # > YOLOv5 configuration
        self._source = str(source)

        # > ALPR variables
        self.license_numbers = {}

        # > Database
        self._connected_timestamp = datetime.now()
        self._status = {}
        self._command = ''
        self._db_ref = TempDb.reference(f"{self.name}/alpr")
        self._db_ref.child("status").listen(self._db_status_callback)
        self._db_ref.child("command").listen(self._db_command_callback)

        # > Process and thread
        self._queue = Queue()
        self._stop_event = Event()
        self._process = Process(
            target=inference,
            daemon=True,
            args=(self.name, self._source, self._queue, self._stop_event)
        )
        self._thread = Thread(
            target=self._update,
            daemon=True
        )

        self._logger.info(
            f"{self.name.title()} ALPR initialized. (source: {self._source})")

    # > Database functions
    def _format_status_db(self):
        return {
            "candidate_key": self.candidate_key(),
            "license_numbers": self.keys()
        }

    def _is_db_difference(self):
        return len(DeepDiff(self._format_status_db(), self._status)) != 0

    def _db_status_callback(self, event: dbEvent):
        self._status = event.data

    def _db_command_callback(self, event: dbEvent):
        self._command = event.data if event.data else ''

    # > Thread functions
    def start(self):
        self._logger.info(f"{self.name.title()} ALPR is starting.")
        if self._process.is_alive():
            return self._logger.warning("Process is already running.")
        self._stop_event.clear()
        self._process.start()
        self._thread.start()

    def stop(self):
        self._logger.info(f"{self.name.title()} ALPR is stopping.")
        self._stop_event.set()
        self._process.join()
        self._thread.join()

    # > Thread logic functions
    def _update(self):
        # initialize value in the databse.
        self._logger.info("Initialize alpr's infos to Realtime Database.")
        self._db_ref.child("status").set(self._format_status_db())
        new_datetime, new_datetime_string = datetime_now()
        self._connected_timestamp = new_datetime
        self._db_ref.child("connected_timestamp").set(new_datetime_string)
        self._db_ref.child("command").set(self._command)

        while self._process.is_alive():  # while inference process is still running.
            while not self._queue.empty():  # if queue has some data.
                # update license_numbers.
                license_number = self._queue.get()
                old_license_number = self.license_numbers.get(license_number)
                self.license_numbers.update(
                    {license_number: old_license_number + 1 if old_license_number else 1})
            if self._is_db_difference():
                self._db_ref.child("status").set(self._format_status_db())
            if seconds_from_now(self._connected_timestamp, 5):
                new_datetime, new_datetime_string = datetime_now()
                self._connected_timestamp = new_datetime
                self._db_ref.child("connected_timestamp").set(
                    new_datetime_string)
            self._command_exec()
        self._logger.info(f"{self.name.title()} ALPR has stopped.")

    def _command_exec(self):
        if self._command != '':
            self._logger.info(f'Received command: {self._command}')
            input = self._command.split(':')
            if hasattr(self, f'_c_{input[0]}'):
                if len(input) == 2:
                    self._logger.info(
                        f'Command Executed. [_c_{input[0]}({input[1]})]')
                    getattr(self, f'_c_{input[0]}')(input[1])
                elif len(input) == 1:
                    self._logger.info(f'Command Executed. [_c_{input[0]}()]')
                    getattr(self, f'_c_{input[0]}')()
            self._db_ref.child('command').set('')

    # > ALPR functions.
    def candidate_key(self):
        if len(list(self.license_numbers.keys())) == 0:
            return ""
        max_value = max(list(self.license_numbers.values()))
        for key, value in self.license_numbers.items():
            if value == max_value:
                return key
        return ""

    def keys(self):
        return list(self.license_numbers.keys())

    def clear(self):
        self._logger.info("Clear ALPR.")
        self.license_numbers.clear()

    def is_detect(self):
        return self.candidate_key() != ""

    def is_running(self):
        return self._process.is_alive()

    def _c_clear(self):
        self.clear()


def main():
    try:
        # Create object.
        alpr = ALPR()
        alpr.start()
        while alpr.is_running():
            pass
    except KeyboardInterrupt:
        alpr.stop()


if __name__ == "__main__":
    main()
