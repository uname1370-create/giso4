import { NextResponse } from 'next/server';
import OpenAI from 'openai';
import { SERVICES_CONTENT } from '@/services-content';
import { saveChatLog } from '@/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const SERVICES_SUMMARY = Object.values(SERVICES_CONTENT)
  .map(
    (s) =>
      `• ${s.title} (${s.titleEn}): ${s.shortDesc} - زمان: ${s.duration} - ماندگاری: ${s.durability}`,
  )
  .join('\n');

const SYSTEM_PROMPT = `تو «غزل - مشاور هوشمند مرکز تخصصی PMU و میکروبلیدینگ عسل رجبی در مشهد» هستی.
شعار برند: «تو زیبایی؛ من فقط کشفش می‌کنم ✨».
لحن گفتار تو: گرم، صمیمی، زنانه، بسیار محترمانه، آرامش‌بخش، کوتاه و ساختارمند (از نوشتن پاراگراف‌های طولانی پرهیز کن).

اطلاعات خدمات مرکز:
${SERVICES_SUMMARY}

خطوط قرمز و قوانین اکید:
۱. هرگز قیمت قطعی نگو! توضیح بده قیمت دقیق پس از مشاهده عکس و وضعیت پوست توسط خانم عسل رجبی تعیین می‌شود.
۲. هرگز تشخیص پزشکی نده. در صورت حساسیت شدید، کلوئید یا بارداری بگو: «عزیزم لطفاً ابتدا با پزشک مشورت کن یا با مشاور انسانی ما در واتساپ در تماس باش».
۳. اگر کاربر گفت می‌خواهد عکسش را تست کند یا مدل را ببیند، او را به دکمه "پیش‌نمایش هوشمند" در سایت تشویق کن.
۴. اگر کاربر مایل به رزرو بود، او را به ثبت اطلاعات در فرم نوبت‌دهی هدایت کن.`;

export async function POST(request: Request) {
  try {
    const { messages, sessionId = 'anonymous' } = await request.json();

    const lastUserMessage = Array.isArray(messages)
      ? messages.filter((m: { role: string }) => m.role === 'user').slice(-1)[0]?.content || ''
      : '';

    const apiKey = process.env.OPENAI_API_KEY;
    let reply = '';

    if (!apiKey) {
      reply =
        'سلام عزیزم، من غزل هستم؛ مشاور هوشمند مرکز عسل رجبی ✨ برای راهنمایی درباره میکروبلیدینگ، شیدینگ لب، خط چشم یا ریمو در خدمتتم. دوست داری اول عکس چهره‌ت رو توی سایت تست کنیم؟';
    } else {
      try {
        const openai = new OpenAI({ apiKey });
        const completion = await openai.chat.completions.create({
          model: process.env.OPENAI_CHAT_MODEL || 'gpt-4o-mini',
          messages: [{ role: 'system', content: SYSTEM_PROMPT }, ...(messages || [])],
          temperature: 0.7,
          max_tokens: 300,
        });
        reply = completion.choices[0]?.message?.content || 'در خدمت شما هستم عزیزم.';
      } catch {
        reply =
          'سلام عزیزم! خوشحال می‌شم کمکت کنم. برای راهنمایی و تعیین نوبت، همکاران ما در واتساپ هم به صورت مستقیم پاسخگوی شما هستند.';
      }
    }

    // ذخیره پیام کاربر و پاسخ در جدول chat_logs
    if (lastUserMessage) {
      try {
        saveChatLog(sessionId, lastUserMessage, reply);
      } catch {
        // نادیده گرفتن خطای لاگ چت در زمان اجرا
      }
    }

    return NextResponse.json({ ok: true, reply });
  } catch (err) {
    return NextResponse.json({
      ok: true,
      reply:
        'سلام عزیزم! در حال حاضر برای مشاوره و تعیین نوبت، همکاران ما در واتساپ به صورت مستقیم در خدمت شما هستند.',
    });
  }
}
