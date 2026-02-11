import fitz  # PyMuPDF
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import argparse
import os

def extract_text_ignore_overlays(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []

    for page in doc:
        text = page.get_text("text") or ""
        pages.append(text.strip())

    doc.close()
    return pages

def process_pdf(pdf_path, input_root, output_root):
    try:
        pages = extract_text_ignore_overlays(pdf_path)

        if not any(pages):
            return (pdf_path, False, "No extractable text")

        relative_path = pdf_path.relative_to(input_root)
        out_dir = output_root / relative_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        out_file = out_dir / f"{pdf_path.stem}_RECOVERED.txt"

        with open(out_file, "w", encoding="utf-8") as f:
            for i, text in enumerate(pages, start=1):
                f.write(f"\n--- PAGE {i} ---\n")
                f.write(text + "\n")

        return (pdf_path, True, None)

    except Exception as e:
        return (pdf_path, False, str(e))

def find_pdfs(path):
    if path.is_file() and path.suffix.lower() == ".pdf":
        return [path]
    return list(path.rglob("*.pdf"))

def main():
    parser = argparse.ArgumentParser(
        description="Recover text from improperly redacted PDFs"
    )
    parser.add_argument("path", help="PDF file or directory")
    parser.add_argument(
        "-o", "--output",
        default="UNREDACTED_OUTPUT",
        help="Output directory"
    )
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=max(1, os.cpu_count() - 1),
        help="Number of worker threads"
    )

    args = parser.parse_args()

    input_root = Path(args.path).resolve()
    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    pdfs = find_pdfs(input_root)

    if not pdfs:
        print("No PDFs found.")
        return

    print(f"[*] Found {len(pdfs)} PDFs")
    print(f"[*] Threads: {args.threads}")
    print(f"[*] Output root: {output_root}")

    results = []

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = [
            executor.submit(process_pdf, pdf, input_root, output_root)
            for pdf in pdfs
        ]

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
            results.append(future.result())

    # Summary
    success = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - success

    print("\n=== SUMMARY ===")
    print(f"Processed: {len(results)}")
    print(f"Recovered: {success}")
    print(f"Failed: {failed}")

    for pdf, ok, err in results:
        if not ok:
            print(f"[FAIL] {pdf}: {err}")

if __name__ == "__main__":
    main()
