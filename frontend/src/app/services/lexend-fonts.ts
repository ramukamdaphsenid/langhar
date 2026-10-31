// PDF font files for PDF generation
const PDF_FONT_FILES = [
  'Lexend-Regular.ttf',
  'Lexend-Bold.ttf',
] as const;

export const lexendFontMap = {
  Lexend: {
    normal: 'Lexend-Regular.ttf',
    bold: 'Lexend-Bold.ttf',
    italics: 'Lexend-Regular.ttf',
    bolditalics: 'Lexend-Bold.ttf',
  },
};

// Optimized font loading with better error handling
async function loadFontAsBase64(fileName: string): Promise<string> {
  const response = await fetch(`/assets/fonts/${fileName}`);
  if (!response.ok) {
    console.warn(`Failed to load PDF font ${fileName}: ${response.status}`);
    throw new Error(`Failed to load PDF font ${fileName}: ${response.status}`);
  }

  const bytes = new Uint8Array(await response.arrayBuffer());

  // Use TypedArray methods for better performance
  let binary = '';
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    const chunk = bytes.subarray(offset, Math.min(offset + chunkSize, bytes.length));
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

export async function loadLexendFontVfs(): Promise<Record<string, string>> {
  const vfs: Record<string, string> = {};

  // Use parallel loading for better performance
  await Promise.all(
    PDF_FONT_FILES.map(async (fileName) => {
      try {
        vfs[fileName] = await loadFontAsBase64(fileName);
      } catch (error) {
        console.error('Font loading failed:', error);
        // Continue without failing the entire font loading process
      }
    }),
  );

  return vfs;
}
