import Foundation
import PDFKit
let url = URL(fileURLWithPath: "/Users/baozhashizitou/Documents/MATHORCUP/work/my-new-contest/problem/2026年MathorCup大数据挑战赛-赛道A初赛.pdf")
if let doc = PDFDocument(url: url) {
    for i in 0..<doc.pageCount {
        if let p = doc.page(at: i), let s = p.string {
            print("=== PAGE \(i+1) ===")
            print(s)
        }
    }
}
