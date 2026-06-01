import type { DemoMockWorldProfile } from "./types/demo";

export type DemoScenarioPreset = {
  label: string;
  mockWorldProfile: DemoMockWorldProfile;
  prompt: string;
};

export const demoScenarioPresets: readonly DemoScenarioPreset[] = [
  {
    label: "亲子",
    mockWorldProfile: "family_afternoon",
    prompt: "今天下午想和妻子、5 岁孩子在附近出门玩几个小时，先安排室内亲子活动，再吃一顿清淡晚餐，不要太远。",
  },
  {
    label: "朋友",
    mockWorldProfile: "friends_gathering",
    prompt: "今天下午想和朋友在附近聚会几个小时，先安排户外散步聊天，再找一家适合分享的轻松晚餐，不要太远。",
  },
  {
    label: "单人",
    mockWorldProfile: "solo_afternoon",
    prompt: "今天下午想一个人在附近轻松待几个小时，先安排轻量活动，再吃一顿清淡的简餐，不要太远。",
  },
  {
    label: "情侣",
    mockWorldProfile: "couple_afternoon",
    prompt: "今天下午想和伴侣在附近出门几个小时，先安排 citywalk，再吃一顿清淡晚餐，不要太远。",
  },
  {
    label: "雨天",
    mockWorldProfile: "rainy_day_fallback",
    prompt: "今天下午想和朋友在附近待几个小时，外面下雨，优先安排室内活动，再找一家热一点的简餐，不要太远。",
  },
  {
    label: "预算",
    mockWorldProfile: "budget_lite",
    prompt: "今天下午想一个人在附近待几个小时，尽量控制预算，先安排免费或低价活动，再吃一顿便宜简餐，不要太远。",
  },
];
