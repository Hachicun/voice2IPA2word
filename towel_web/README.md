# Leo Tháp (bản web)

Bản web của `python app.py --game`, chạy trên điện thoại (màn hình dọc). Trang đọc một từ tiếng Anh (bản ghi giọng Mỹ của Wiktionary), bạn bấm 🎤 và nói lại. Nói đúng thì leo lên tháp, sai thì rơi về phía dung nham. Luật chơi giống hệt `tower.py`.

Phát âm được chấm **ngay trong trình duyệt** bằng model ZIPA (cùng file `model.int8.onnx`, chạy bằng onnxruntime-web). Phần đoán âm, so khớp IPA và chấm CTC trên cả từ điển 40 000 từ được chuyển từ `app.py` / `ipa_us.py` sang JS. Giọng bạn không gửi đi đâu cả.

## Đưa lên GitHub Pages

1. Tạo repo mới trên GitHub, rồi đẩy **nội dung thư mục này** lên nhánh `main`. Thư mục `tools/` không cần cho trang chạy.
2. Vào Settings → Pages → Source: *Deploy from a branch*, chọn `main` và `/ (root)`.
3. Mở `https://<tên>.github.io/<repo>/` trên điện thoại.

Lưu ý:

- `model/model.int8.onnx` nặng 71 MB. GitHub cảnh báo file lớn hơn 50 MB, nhưng vẫn nhận vì dưới giới hạn 100 MB. **Không dùng Git LFS**, vì GitHub Pages sẽ phục vụ file con trỏ LFS thay cho model.
- Không tải lên bằng cách kéo thả trên trang GitHub: trình duyệt chỉ nhận file dưới 25 MB. Hãy dùng `git push`.
- Chỉ đẩy thư mục `towel_web/`. Đừng đẩy cả dự án cha, vì `recordings/` chứa giọng của bạn, ngoài ra còn `logs/` và `.venv/`.
- Cần trình duyệt mới (iOS 16.4+ / Safari, Chrome Android bản gần đây): onnxruntime-web chỉ có bản wasm SIMD.
- Lần đầu mở trang, điện thoại tải 71 MB. Model được lưu vào Cache API, nên các lần sau không phải tải lại.
- Micro chỉ hoạt động trên HTTPS hoặc localhost. GitHub Pages là HTTPS nên không cần làm gì thêm.
- onnxruntime-web 1.31.1 được nạp từ cdn.jsdelivr.net. Bản ghi từ mẫu tải thẳng từ upload.wikimedia.org (mp3), không gọi API. Nếu tải lỗi (mất mạng…), giọng máy của điện thoại đọc thay.

## Chạy thử trên máy

```bash
cd towel_web && python3 -m http.server 8000
```

Mở `http://localhost:8000`. Thêm `?nomic` để xem giao diện mà không xin quyền micro, hoặc `?sfx=0` để tắt tiếng hiệu ứng.

## Cách chơi

- **3 mức**, như `--level` của bản terminal: **Dễ** (zipf ≥ 5, 972 từ), **Trung bình** (zipf ≥ 4, 5 140 từ), **Khó** (zipf 3–4, 6 798 từ). Chỉ dùng từ có bản ghi giọng Mỹ. Chọn mức ở màn hình đầu; hết ván thì chọn lại ở hàng nút dưới. Trang nhớ mức lần trước.
- **Bấm 🎤 rồi nói, nói xong bấm lần nữa** để dừng và chấm (trang không tự dừng). Thanh nhỏ trong nút cho thấy micro đang nghe. Trên máy tính dùng phím Space. Nếu micro chưa bật, nút hiện **BẬT MICRO**: bấm để xin quyền lại.
- Micro bị chặn trên Mac: bấm biểu tượng micro/🔒 ở thanh địa chỉ để cho phép, và bật trình duyệt trong System Settings → Privacy & Security → Microphone.
- Đúng ngay lần đầu được +2 tầng, đúng sau vài lần được +1. Gần đúng (60–89 %) thì đứng yên, sai thì rơi 1 tầng.
- Một lần nói được tính là **đúng** khi giống từ 90 % âm trở lên, hoặc khi model xếp từ đích đứng đầu cả từ điển.
- **Đáp án** hoặc **Từ mới** khi chưa nói đúng: −2 tầng. Sau khi xem đáp án, bạn có thể luyện tiếp thoải mái mà không bị trừ.
- Cứ 5 từ đúng ngay lần đầu thì được 1 lượt cược. Cược trước khi nói: từ dễ +4/−4, từ khó +8/−10.
- Phím tắt trên máy tính: R nghe lại · S nghe chậm · C cược · A đáp án · N từ mới.

## Khác với bản terminal

- Bản terminal mặc định chấm bằng Koel + ZIPA. Bản web chỉ có ZIPA, nên thứ hạng của từ đích có thể khác một chút.
- onnxruntime-web (wasm) tính model int8 hơi khác onnxruntime trên máy tính. Trên 30 bản ghi thử, phần chấm điểm cho kết quả giống hệt Python khi dùng cùng đầu ra model. Tính cả model thì 28/30 lần cho cùng kết luận đúng / gần đúng / sai.
- Giao diện là HTML + `style.css`; chỉ có tháp được vẽ trên `<canvas>` (nét theo devicePixelRatio). Bố cục dọc cho điện thoại, chừa tai thỏ / thanh home (`safe-area-inset`), tự chuyển sang 2 cột khi màn hình ngang hoặc máy tính.

## Cập nhật dữ liệu

Bảng bản ghi giọng Mỹ `data/audio_us.json` ({từ: đường dẫn mp3 trên Commons}) dựng sẵn từ bản dump Wiktionary của kaikki.org, giống cách của `english_dictionary`. Chạy từ thư mục gốc dự án `voice2IPA2word`:

```bash
python3 build_audio.py
```

Rồi xuất dữ liệu cho bản web (dùng `.venv` của `app.py`):

```bash
V2I_MODEL=zipa .venv/bin/python towel_web/tools/export_web.py
```

Kiểm tra bản JS so với Python, dùng onnxruntime-web trong Node:

```bash
V2I_MODEL=zipa .venv/bin/python towel_web/tools/ref_dump.py 30 /tmp/ref
```

```bash
npm i --prefix /tmp/ortweb onnxruntime-web@1.31.1
```

```bash
node towel_web/tools/check_core.js /tmp/ref /tmp/ortweb/node_modules
```

## Nguồn và giấy phép

- Model nhận âm: [ZIPA small (anyspeech/zipa-small-crctc-300k)](https://huggingface.co/anyspeech/zipa-small-crctc-300k), CC BY 4.0.
- Bản ghi từ mẫu: Wikimedia Commons / Wiktionary (Lingua Libre và các tác giả khác), theo giấy phép của từng file. Tên người đọc và giấy phép hiện khi xem đáp án.
- Nghĩa tiếng Việt: Wiktionary tiếng Việt (kaikki.org, CC BY-SA) và từ điển OVDP. Phát âm: CMUdict, espeak-ng.
