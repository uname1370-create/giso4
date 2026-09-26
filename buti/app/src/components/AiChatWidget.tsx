'use client';

/**
 * ویجت چت هوشمند «غزل» — دستیار مجازی مرکز عسل رجبی
 * مجهز به Smart Actions زنده برای تغییر گام‌های ویزارد سایت اصلی
 */

import React, { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { HERO_IMAGE_URL, buildHeroWhatsAppLink } from '@/options';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AiChatWidgetProps {
  planTier?: 'bronze' | 'silver' | 'gold';
  customAssistantName?: string;
}

export const AiChatWidget: React.FC<AiChatWidgetProps> = ({
  planTier = 'gold',
  customAssistantName,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // در پلن برنزی، چت‌بات غیرفعال است
  if (planTier === 'bronze') {
    return null;
  }

  const assistantTitle =
    planTier === 'gold' && customAssistantName
      ? customAssistantName
      : 'غزل • مشاور هوشمند عسل رجبی';

  useEffect(() => {
    try {
      const saved = localStorage.getItem('asal_chat_history');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed.slice(-10));
          return;
        }
      }
    } catch {
      // نادیده گرفتن خطا
    }

    setMessages([
      {
        role: 'assistant',
        content:
          'سلام عزیزم ✨ من غزل هستم، مشاور هوشمند مرکز عسل رجبی. هر سوالی درباره مدل‌های میکروبلیدینگ، شیدینگ لب یا ریمو داری بپرس تا کمکت کنم!',
      },
    ]);
  }, []);

  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem('asal_chat_history', JSON.stringify(messages.slice(-10)));
      } catch {
        // نادیده گرفتن خطا
      }
    }
    if (isOpen) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || inputValue).trim();
    if (!text || isLoading) return;

    const newMsgs: ChatMessage[] = [...messages, { role: 'user', content: text }];
    setMessages(newMsgs);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: newMsgs.slice(-10),
          sessionId: 'client_session',
        }),
      });
      const data = await res.json();
      if (data.ok && data.reply) {
        setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'مشکلی در ارتباط پیش آمد، می‌توانید با مشاور انسانی ما در واتساپ صحبت کنید.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  /** اکشن‌های هوشمند: هدایت زنده ویزارد صفحه به گام مورد نظر */
  const triggerWizardStep = (stepNumber: number) => {
    window.dispatchEvent(
      new CustomEvent('set_wizard_step', { detail: { step: stepNumber } }),
    );
  };

  return (
    <div className="fixed bottom-6 left-6 z-[9999] font-[family-name:var(--font-vazirmatn)]">
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2.5 px-4 py-3 rounded-full bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 text-neutral-950 font-bold text-xs shadow-2xl shadow-amber-500/40 hover:scale-105 active:scale-95 transition-all border border-amber-300 cursor-pointer"
        >
          <div className="relative w-6 h-6 rounded-full overflow-hidden border border-neutral-950/40">
            <Image src={HERO_IMAGE_URL} alt="غزل" fill className="object-cover" unoptimized />
          </div>
          <span>گفتگو با غزل (مشاور هوشمند) ✨</span>
          <span className="w-2 h-2 rounded-full bg-emerald-600 animate-ping" />
        </button>
      )}

      {isOpen && (
        <div className="w-[330px] sm:w-[370px] h-[500px] bg-neutral-900/95 border border-amber-500/40 rounded-2xl shadow-2xl flex flex-col overflow-hidden backdrop-blur-2xl animate-fadeIn">
          {/* Header */}
          <div className="p-3.5 bg-neutral-950 border-b border-neutral-800 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="relative w-8 h-8 rounded-full overflow-hidden border border-amber-400">
                <Image src={HERO_IMAGE_URL} alt="غزل" fill className="object-cover" unoptimized />
              </div>
              <div>
                <p className="text-xs font-bold text-neutral-100">{assistantTitle}</p>
                <p className="text-[10px] text-emerald-400">پاسخگویی برخط هوشمند</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-neutral-400 hover:text-neutral-100 text-sm p-1.5 cursor-pointer"
            >
              ✕
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 p-3.5 overflow-y-auto space-y-3 text-xs">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[84%] p-3 rounded-2xl leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-amber-500 text-neutral-950 rounded-bl-none font-medium'
                      : 'bg-neutral-800 text-neutral-200 rounded-br-none border border-neutral-700/60 shadow-sm'
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="p-2.5 rounded-xl bg-neutral-800 text-neutral-400 text-[11px] flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce" />
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce [animation-delay:0.4s]" />
                  <span className="ms-1">غزل در حال نوشتن است...</span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Smart Actions (اقدامات هوشمند زنده متصل به ویزارد) */}
          <div className="px-3 py-2 bg-neutral-950/70 border-t border-neutral-800/80 flex items-center gap-1.5 overflow-x-auto text-[10px]">
            <button
              onClick={() => {
                void handleSend('می‌خوام مدلم رو روی چهره‌ام تست کنم');
                triggerWizardStep(1); // هدایت مستقیم ویزارد به Step 1 (انتخاب خدمت)
              }}
              className="px-2.5 py-1 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 hover:bg-amber-500/30 whitespace-nowrap cursor-pointer transition-all"
            >
              🪄 تست مدل روی چهره
            </button>
            <button
              onClick={() => {
                void handleSend('می‌خوام نوبت بگیرم');
                triggerWizardStep(5); // هدایت مستقیم ویزارد به Step 5 (فرم رزرو نوبت)
              }}
              className="px-2.5 py-1 rounded-full bg-neutral-800 text-neutral-300 hover:bg-neutral-700 whitespace-nowrap cursor-pointer transition-all"
            >
              📅 رزرو نوبت
            </button>
            <a
              href={buildHeroWhatsAppLink()}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2.5 py-1 rounded-full bg-emerald-950 border border-emerald-700 text-emerald-300 whitespace-nowrap"
            >
              💬 واتساپ مشاور
            </a>
          </div>

          {/* Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleSend();
            }}
            className="p-2.5 bg-neutral-950 border-t border-neutral-800 flex gap-2"
          >
            <input
              type="text"
              placeholder="از غزل بپرسید..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="flex-1 px-3 py-2 rounded-xl bg-neutral-900 border border-neutral-800 text-xs text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-amber-400"
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs disabled:opacity-40 transition-all cursor-pointer"
            >
              ارسال
            </button>
          </form>
        </div>
      )}
    </div>
  );
};
