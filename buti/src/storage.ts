import fs from 'node:fs/promises';
import path from 'node:path';

/**
 * ذخیره تصاویر کاربر و خروجی در پوشه public/uploads/leads/[leadId]/
 */
export async function saveLeadImage(
  leadId: string,
  filename: 'original' | 'result',
  dataUriOrBase64: string,
): Promise<string | null> {
  if (!dataUriOrBase64) return null;

  try {
    const uploadDir = path.join(process.cwd(), 'public', 'uploads', 'leads', leadId);
    await fs.mkdir(uploadDir, { recursive: true });

    let extension = 'png';
    let base64Data = dataUriOrBase64;

    const match = /^data:(image\/[a-zA-Z0-9+.-]+);base64,(.+)$/.exec(dataUriOrBase64);
    if (match) {
      const mime = match[1];
      base64Data = match[2];
      if (mime.includes('jpeg') || mime.includes('jpg')) extension = 'jpg';
      else if (mime.includes('webp')) extension = 'webp';
      else if (mime.includes('svg')) extension = 'svg';
    }

    const targetFile = `${filename}.${extension}`;
    const fullPath = path.join(uploadDir, targetFile);
    await fs.writeFile(fullPath, Buffer.from(base64Data, 'base64'));

    return `/uploads/leads/${leadId}/${targetFile}`;
  } catch (error) {
    console.error('[STORAGE_ERROR] Failed to save image:', error);
    return null;
  }
}
