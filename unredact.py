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

def extract_images(pdf_path, out_dir):
    """Extract all embedded images from the PDF, saved as PNGs."""
    doc = fitz.open(pdf_path)
    image_count = 0

    for page_num, page in enumerate(doc, start=1):
        for img_index, img in enumerate(page.get_images(full=True), start=1):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                img_ext = base_image["ext"]  # e.g. "png", "jpeg"

                img_filename = out_dir / f"page{page_num}_img{img_index}.{img_ext}"
                with open(img_filename, "wb") as f:
                    f.write(img_bytes)

                image_count += 1
            except Exception:
                pass  # Skip unreadable image xrefs

    doc.close()
    return image_count

def process_pdf(pdf_path, input_root, output_root):
    try:
        pages = extract_text_ignore_overlays(pdf_path)

        relative_path = pdf_path.relative_to(input_root)
        out_dir = output_root / relative_path.parent / pdf_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        has_text = any(pages)
        if has_text:
            out_file = out_dir / f"{pdf_path.stem}_RECOVERED.txt"
            with open(out_file, "w", encoding="utf-8") as f:
                for i, text in enumerate(pages, start=1):
                    f.write(f"\n--- PAGE {i} ---\n")
                    f.write(text + "\n")

        image_count = extract_images(pdf_path, out_dir)

        if not has_text and image_count == 0:
            return (pdf_path, False, "No extractable text or images")

        return (pdf_path, True, None, image_count)

    except Exception as e:
        return (pdf_path, False, str(e), 0)

def find_pdfs(path):
    if path.is_file() and path.suffix.lower() == ".pdf":
        return [path]
    return list(path.rglob("*.pdf"))

def main():
    parser = argparse.ArgumentParser(
        description="Recover text and images from improperly redacted PDFs"
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

    success = sum(1 for r in results if r[1])
    failed = len(results) - success
    total_images = sum(r[3] for r in results if r[1])

    print("\n=== SUMMARY ===")
    print(f"Processed: {len(results)}")
    print(f"Recovered: {success}")
    print(f"Failed:    {failed}")
    print(f"Images extracted: {total_images}")

    for r in results:
        if not r[1]:
            print(f"[FAIL] {r[0]}: {r[2]}")

if __name__ == "__main__":
    main()