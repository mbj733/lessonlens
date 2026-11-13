export const STRINGS = {
  en: {
    app: 'LessonLens',
    tagline: 'deck → grounded 3D scene',
    deck: 'Deck',
    hint: 'Click an object to see the slide it came from',
    loading: 'Loading scene…',
    noSelection: 'Nothing selected yet.',
    tasks: 'Tasks',
    page: 'page',
    source: 'source',
    correct: 'Correct',
    wrong: 'Not quite — try again',
    solved: 'Solved',
    kindDefinition: 'definition',
    kindConcept: 'concept',
    kindExample: 'example',
    kindTable: 'table / example',
    kindSummary: 'summary',
    objects: 'objects',
    quizPrompt: 'Every object is a claim; click one to read its source quote.',
  },
  zh: {
    app: 'LessonLens',
    tagline: '讲义 → 可溯源的 3D 场景',
    deck: '讲义',
    hint: '点击任意物体，查看它来自哪一页原文',
    loading: '正在加载场景…',
    noSelection: '还没有选中物体。',
    tasks: '练习',
    page: '第',
    source: '出处',
    correct: '正确',
    wrong: '再想想',
    solved: '已完成',
    kindDefinition: '定义',
    kindConcept: '概念',
    kindExample: '例子',
    kindTable: '表格 / 例子',
    kindSummary: '总结',
    objects: '个物体',
    quizPrompt: '每个物体对应一条主张，点击即可读原文出处。',
  },
};

let current = 'en';

export function lang() {
  return current;
}

export function t(key) {
  return STRINGS[current][key] ?? STRINGS.en[key] ?? key;
}

export function applyLang(next) {
  current = STRINGS[next] ? next : 'en';
  document.documentElement.lang = current === 'zh' ? 'zh-CN' : 'en';
  for (const node of document.querySelectorAll('[data-i18n]')) {
    const key = node.dataset.i18n;
    node.textContent = t(key);
  }
  const toggle = document.getElementById('lang-toggle');
  if (toggle) toggle.textContent = current === 'en' ? '中文' : 'English';
  document.dispatchEvent(new CustomEvent('lessonlens:lang', { detail: current }));
  return current;
}
