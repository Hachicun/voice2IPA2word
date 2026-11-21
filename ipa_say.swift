// Đọc chuỗi IPA bằng giọng có sẵn của macOS (AVSpeechSynthesizer), ghi ra WAV.
// app.py tự biên dịch file này (swiftc có sẵn trong Xcode Command Line Tools) khi cần.
//
//   ipa_say --voice "Ava (Premium)" [--rate 0.5] --out <thư mục> <ipa1> [<ipa2> ...]
//     -> <thư mục>/0.wav, 1.wav ... (mỗi chuỗi IPA một file)
//   ipa_say --list   -> liệt kê giọng tiếng Anh: tên (chất lượng) <tab> identifier
import AVFoundation

func pickVoice(_ want: String) -> AVSpeechSynthesisVoice? {
    // Tên giọng giống lệnh `say -v '?'`: "Ava (Premium)", "Samantha"... (đã gồm chất lượng)
    let en = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("en") }
    return en.first { $0.name == want && $0.language == "en-US" }
        ?? en.first { $0.name == want }
        ?? AVSpeechSynthesisVoice(language: "en-US")
}

let synth = AVSpeechSynthesizer()

func render(ipa: String, voice: AVSpeechSynthesisVoice?, rate: Float, out: URL) -> Bool {
    let text = NSMutableAttributedString(string: "word")
    text.addAttribute(NSAttributedString.Key(rawValue: AVSpeechSynthesisIPANotationAttribute),
                      value: ipa, range: NSRange(location: 0, length: text.length))
    let u = AVSpeechUtterance(attributedString: text)
    u.voice = voice
    u.rate = rate
    var file: AVAudioFile?
    var ok = false
    let done = DispatchSemaphore(value: 0)
    synth.write(u) { buf in
        guard let pcm = buf as? AVAudioPCMBuffer else { return }
        if pcm.frameLength == 0 { done.signal(); return }
        if file == nil {
            let settings: [String: Any] = [AVFormatIDKey: kAudioFormatLinearPCM,
                                           AVSampleRateKey: pcm.format.sampleRate,
                                           AVNumberOfChannelsKey: 1,
                                           AVLinearPCMBitDepthKey: 16,
                                           AVLinearPCMIsFloatKey: false]
            file = try? AVAudioFile(forWriting: out, settings: settings,
                                    commonFormat: pcm.format.commonFormat,
                                    interleaved: pcm.format.isInterleaved)
        }
        if (try? file?.write(from: pcm)) != nil { ok = true }
    }
    while done.wait(timeout: .now() + 0.02) == .timedOut {
        RunLoop.current.run(until: Date() + 0.02)
    }
    file?.close()          // ghi xong phần đầu WAV (closure vẫn giữ file nên không tự đóng)
    file = nil
    return ok
}

var args = Array(CommandLine.arguments.dropFirst())
if args.first == "--list" {
    for v in AVSpeechSynthesisVoice.speechVoices() where v.language.hasPrefix("en") {
        print("\(v.name)\t\(v.language)\t\(v.identifier)")
    }
    exit(0)
}
var voiceName = "", rate = AVSpeechUtteranceDefaultSpeechRate, outDir = "."
var items: [String] = []
while !args.isEmpty {
    let a = args.removeFirst()
    switch a {
    case "--voice": voiceName = args.isEmpty ? "" : args.removeFirst()
    case "--rate": rate = Float(args.isEmpty ? "" : args.removeFirst()) ?? rate
    case "--out": outDir = args.isEmpty ? "." : args.removeFirst()
    default: items.append(a)
    }
}
let voice = pickVoice(voiceName)
var failed = false
for (i, ipa) in items.enumerated() {
    let url = URL(fileURLWithPath: outDir).appendingPathComponent("\(i).wav")
    if !render(ipa: ipa, voice: voice, rate: rate, out: url) {
        FileHandle.standardError.write("không đọc được: \(ipa)\n".data(using: .utf8)!)
        failed = true
    }
}
exit(failed ? 1 : 0)
