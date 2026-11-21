# Ý tưởng game phát âm: khung 3 lớp

Ghi lại từ buổi thảo luận ngày 2026-11-20. Chưa phải là thiết kế đã chốt, trừ phần "Đã làm".

## Khung 3 lớp

- **Hạt nhân** (đã có trong `app.py`): nhận âm thanh → nhận ra chuỗi âm vị → so khớp với từ đích → điểm % kèm âm nào sai. Hạt nhân có cả chiều ngược lại: từ chuỗi âm nghe được, tìm ra từ gần nhất (`find_words`).
- **Vỏ trong**: người chơi **nói thế nào**, tức là nhận gợi ý gì và phải nói ra cái gì.
- **Vỏ ngoài**: **cách chơi**, cách tính điểm, thưởng phạt, thắng thua.

**Hợp đồng giữa các lớp.** Vỏ ngoài chỉ nhận **4 mức kết quả** (đúng ngay, đúng, gần đúng, sai), kèm độ khó của lượt đó. Leo tháp đang dùng đúng 4 mức này. Nhờ vậy, vỏ trong nào cũng ghép được với vỏ ngoài nào.

**Vỏ trong cần thêm một thứ là "lăng kính chấm".** Ngoài chấm cả từ, vỏ trong có thể chỉ soi một phần: âm cuối, nguyên âm, hoặc một âm cụ thể. Đây là chỗ mở ra nhiều kiểu luyện khác nhau.

---

## Vỏ trong: nói thế nào

Xếp theo 2 trục: **đầu vào** (người chơi nhận gợi ý gì) và **độ tự do** (nói đúng một từ, hay tự nghĩ ra từ).

| # | Tên | Cách chơi | Luyện kỹ năng |
|---|---|---|---|
| 1 | **Nhại** (đã có: `--guess`, `--game`) | Nghe 1 từ rồi nói theo | Bắt chước âm |
| 2 | **Đọc chữ** | Chỉ thấy chữ, không nghe mẫu | Quy tắc từ chữ ra âm, chữ câm (knife, island) |
| 3 | **Đọc IPA** | Chỉ thấy /θɪŋk/ | Đọc được ký hiệu IPA |
| 4 | **Nghĩa → Từ** | Thấy "con cá" thì nói *fish* | Nhớ từ và phát âm cùng lúc |
| 5 | **Cặp tối thiểu** ⭐ | Hiện *ship / sheep* và đánh dấu một từ. Nói sao cho máy chấm gần từ đó hơn từ kia | Phân biệt /iː–ɪ/, /θ–s/, /l–r/, /æ–e/, /ʃ–s/ |
| 6 | **Đuôi** ⭐ | Chỉ chấm âm cuối: cats/dogs/buses, walked/played/wanted | Âm cuối, lỗi số 1 của người Việt |
| 7 | **Săn âm** (đã có: `--hunt`) | Tự nói một từ bất kỳ có âm /θ/ | Tự tạo ra âm, không dựa vào mẫu |
| 8 | **Vần** | Nói một từ vần với *light*: bite, write, height | Nguyên âm. Nhận ra chữ khác nhau mà âm giống nhau |
| 9 | **Nối âm** | Từ sau bắt đầu bằng **âm** cuối của từ trước (knife kết thúc bằng /f/, nên tiếp *phone*) | Biết âm khác chữ |
| 10 | **Biến hình** | Mỗi bước chỉ đổi 1 âm vị: ship → sheep → cheap → chip | Nhận biết từng âm vị |
| 11 | **Ghép âm** | Máy đọc rời /k/…/æ/…/t/, người chơi nói liền thành từ | Ghép âm |
| 12 | **Trí nhớ** | Nghe 3 từ, nói lại đúng thứ tự (số từ tăng dần) | Trí nhớ âm thanh |
| 13 | **Trọng âm (gián tiếp)** | PHOtograph / phoTOgrapher. Không đo trọng âm trực tiếp mà soi nguyên âm có bị rút thành /ə/ hay không | Trọng âm, âm rút gọn |

Hai vỏ đáng làm trước là **5 (cặp tối thiểu)** và **6 (đuôi)**: đúng chỗ người Việt hay sai, và hạt nhân làm được ngay. Với cặp tối thiểu, chỉ cần chấm với cả hai từ rồi xem gần từ nào hơn. Các vỏ 7–10 dùng chiều ngược của hạt nhân (người chơi tự nói rồi tìm từ), nên tận dụng được thứ đã có.

---

## Vỏ ngoài: cách chơi

Có 2 loại:
- **Chill**: không căng thẳng, ví dụ Chòm sao. Chưa kiểm chứng người dùng có thích hay không.
- **Tranh đấu**: có mốc thắng thua rõ ràng, ví dụ Leo tháp. Bắt buộc:
  - thắng thua **không giới hạn thời gian**, để thoải mái sai và thoải mái luyện;
  - có thưởng phạt, thắng thua rõ ràng.

### Chẩn đoán game câu cá
Game câu cá sai không phải vì ý tưởng mà vì **thế giới chạy theo đồng hồ**. Cách sửa là **thời gian theo lượt**: cá chỉ bơi một bước sau mỗi lần người chơi nói. Vẫn có cảm giác áp lực, nhưng không có giờ, nên người chơi được suy nghĩ và tập thoải mái. Nguyên tắc này áp dụng cho mọi vỏ ngoài.

### Tâm lý học cần khai thác
- **Vòng lặp ngắn, phản hồi "sướng" ngay** (3–5 giây mỗi lượt): âm thanh, màu, rung khung. Tháp làm tốt việc này.
- **Suýt trúng** (near-miss): "gần đúng" kèm chỉ rõ âm nào lệch. Người chơi thấy "chỉ thiếu chút" nên muốn thử lại.
- **Sợ mất** (loss aversion): mất thứ đang có đau hơn không được thêm. Rơi tầng hiệu quả vì lý do này.
- **Gần đích thì hăng** (goal gradient) và **tiến độ có sẵn** (endowed progress): bắt đầu từ tầng 50 thay vì 0 là đúng tâm lý.
- **Thêm một ván nữa**: mỗi ván 2–5 phút, kết thúc rõ, bấm chơi lại ngay.
- **Đặt cược** (push your luck): tự quyết chốt điểm hay liều tiếp. Đây là một trong những cơ chế gây nghiện mạnh nhất.
- **Thưởng ngẫu nhiên** nhưng gắn với kỹ năng: thỉnh thoảng rơi bùa hoặc từ vàng.
- **Vùng flow**: tự điều chỉnh độ khó để tỉ lệ đúng khoảng 70–85%.

### ⚠️ Quy tắc phạt riêng cho game phát âm
Máy nhận dạng **sẽ có lúc chấm sai**. Bị phạt oan là thứ giết cảm giác nghiện nhanh nhất. Vì vậy:
1. Chỉ phạt khi **sai rõ ràng**. "Gần đúng" thì giữ nguyên, không phạt.
2. Luôn hiện **IPA máy nghe được** để người chơi thấy kết quả là công bằng.
3. Phạt vào vị trí hoặc tài nguyên, **không xoá công sức tích luỹ**.
4. Được thử lại cùng một từ, nhưng thưởng giảm dần (tháp: lần đầu +2, sau đó +1).

### Các vỏ ngoài tranh đấu (theo lượt, thắng thua rõ ràng)

| Tên | Luật tóm tắt | Điểm mạnh tâm lý |
|---|---|---|
| **Leo tháp** (đã có) | Lên 100 thắng, rơi xuống 0 thua | Chuẩn mực để so |
| **Đấu Boss** ⭐ | Boss có thanh máu, người chơi có 3–5 tim. Đúng ngay là chí mạng, đúng là đánh trúng, gần đúng là trượt, sai thì mất tim. Mỗi boss có **điểm yếu là một âm**: "Rồng TH" nhận gấp đôi sát thương từ từ có /θ/. Chuỗi boss là lộ trình học | Mục tiêu rõ, sợ mất tim, lộ trình theo âm. Ghép rất hợp với vỏ cặp tối thiểu |
| **Caro với máy** ⭐ | Mỗi ô có một từ. Muốn đánh ô nào phải đọc đúng từ đó; đọc sai là mất lượt và máy đi tiếp. 5 ô liền là thắng | Ai ở Việt Nam cũng biết luật. Có chiến thuật (chọn từ dễ hay chặn đường máy). Không có giờ |
| **Két sắt** (đặt cược) | Mỗi từ đúng cộng điểm vào két, hệ số nhân tăng dần. Có thể **chốt** bất cứ lúc nào; sai một từ là mất cả két chưa chốt. Đủ 1000 điểm đã chốt là thắng, hết 3 mạng là thua | Cơ chế liều mạnh nhất. Người chơi tự chỉnh độ khó qua việc chọn từ khó để có hệ số cao |
| **Thủ thành theo lượt** (cứu game cá) | Quái hoặc cá mang từ và IPA, tiến 1 bước sau mỗi lượt. Đọc đúng là bắn hạ, từ khó là quái to | Áp lực nhưng không có giờ. Đúng luật cá của bạn |
| **Rắn & thang** | Đúng ngay đi 2 lần số xúc xắc, sai gặp rắn | Có may rủi, rất đơn giản |

**Két sắt** còn có thể làm **lớp phụ gắn vào game khác**, ví dụ trong tháp được "liều" để nhảy +3.

### Vỏ chill (cần kiểm chứng)
Gồm Chòm sao (đã có), **Vườn âm** (mỗi âm vị là một cây, luyện thì cây lớn, bỏ lâu thì cây héo nhẹ) và **Album sưu tầm** (sưu tầm từ hoặc âm). Cách kiểm chứng rẻ: thư mục `logs/` đã có, chỉ cần ghi thêm **độ dài mỗi phiên và số lần quay lại** của từng chế độ rồi so chill với tranh đấu.

### Tầng meta (nối các game lại)
- **Bản đồ 44 âm vị**, tô màu theo độ chính xác. Đây là "bộ sưu tập" xuyên suốt.
- **Từ nợ**: từ đọc sai sẽ quay lại trong game sau dưới dạng boss, cá hoặc ô caro. Đây là ôn tập ngắt quãng (SRS) giấu trong trò chơi.
- **Chuỗi ngày** có "đóng băng" để lỡ một ngày không mất chuỗi, cộng với **kỷ lục cá nhân**.

---

## Đề xuất thứ tự làm
1. **Đấu Boss + Cặp tối thiểu/Đuôi**: giá trị học cao nhất, kế thừa cảm giác tốt của tháp.
2. **Caro + Đọc chữ**: luật quen thuộc, có chiến thuật, thắng thua rõ.
3. Làm lại game cá thành **thủ thành theo lượt**.
4. Ghi số liệu để quyết có giữ hướng chill hay không.

---

## Đã làm: luật leo tháp (`--game`, 2026-11-20)

Nguyên tắc người dùng chốt: **giữ luật đơn giản**. Đã bỏ các ý "kiên trì", "xu" và "thưởng ngẫu nhiên".

- **Cơ bản:** đúng ngay +2, đúng sau vài lần +1, gần đúng 0, sai −1.
- **Bỏ từ** (A hoặc N khi chưa nói đúng): −2 tầng, mất combo, mỗi từ một lần. Sau khi bấm A, luyện tự do, không bị trừ.
- **Lượt cược:** cứ đủ 5, 10, 15… từ nói đúng ngay lần đầu thì nhặt 1 lượt, không phân dễ hay khó.
- **Cược (phím C):** chỉ trước lần nói đầu; cứ cược là mất lượt cược.

  | Loại từ | Đúng | Gần đúng | Sai |
  |---|---|---|---|
  | Dễ (1 âm tiết) | +4 | 0 | −4 |
  | Khó (≥ 2 âm tiết) | +8 | 0 | −10 |

- **Combo** (chỉ nhân điểm, tối đa ×5): mỗi mức một màu nhân vật, gồm ×1 trắng, ×2 xanh lá, ×3 xanh ngọc, ×4 tím hồng, ×5 vàng. Mất combo thì nhân vật xám một lát. Người dùng không muốn hiệu ứng màu mè rườm rà.
- Các con số nằm ở đầu `tower.py`: `GIVE_UP`, `MILESTONE`, `BET`, `TIER_FG`.

**Cần theo dõi:** theo log ngày 2026-11-20, từ 1 âm tiết đúng ngay **27%**, còn từ ≥ 2 âm tiết đúng ngay **39%**. Nghĩa là với model, từ "khó" lại dễ hơn. Mẫu còn nhỏ, nhưng cần đọc log `game_bet` xem cược từ khó có bị dễ thắng quá không.
