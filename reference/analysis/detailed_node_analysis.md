# Coze沉浸式历史故事工作流 - 详细节点分析

## 工作流概述

这是一个包含28个节点的复杂视频生成工作流，完整实现了从主题输入到视频输出的全自动化流程。每个节点都有具体的功能和参数配置。

## 详细节点分析

### 1. 输入处理阶段

#### Node 142052 - 输出节点（开始提示）
**节点类型**: type: 13 (输出节点)  
**功能**: 显示开始生成故事文案的提示信息  
**配置**:
```json
{
    "content": "开始生成故事文案...",
    "streamingOutput": false,
    "callTransferVoice": true,
    "chatHistoryWriting": "historyWrite"
}
```
**作用**: 用户体验提示，告知用户工作流开始执行

---

### 2. 内容生成阶段

#### Node 121343 - 大模型_根据主题生成文案
**节点类型**: type: 3 (LLM节点)  
**核心功能**: 根据用户输入主题生成完整的历史故事文案  

**详细配置**:
```json
{
    "llmParam": {
        "modleName": "DeepSeek-V3",
        "modelType": 1738675210,
        "temperature": 0.8,
        "maxTokens": 1024,
        "responseFormat": 1,
        "generationDiversity": "default_val"
    }
}
```

**Prompt分析**:
```
根据主题：{{主题}}，生成一个1000字左右的沉浸式历史故事，采用以下结构：

1. 悬念开场（100字）：用疑问句开头，制造悬念
2. 身份代入（200字）：第二人称"你"，让观众代入历史人物
3. 冲突升级（300字）：描述历史事件的核心矛盾
4. 破局细节（300字）：揭示关键转折点的细节
5. 主题收尾（100字）：点明历史意义

要求：
- 大量使用感官描写（视觉、听觉、触觉）
- 多用短句，营造紧张节奏
- 每段不超过3句话
- 加入历史专业术语
- 情感渲染要到位
```

**输出示例结构**:
```
真的吗？一个小小的决定竟然改变了整个王朝的命运？

你是春秋时期的一名普通士兵。此刻你站在城墙上，看着远方滚滚而来的烟尘...
```

---

#### Node 1199098 - 大模型_主题生成
**节点类型**: type: 3 (LLM节点)  
**核心功能**: 从生成的文案中提取2个字的主题标题  

**详细配置**:
```json
{
    "llmParam": {
        "modleName": "DeepSeek-V3",
        "modelType": 1738675210,
        "temperature": 1.0,
        "maxTokens": 512,
        "responseFormat": 1
    }
}
```

**Prompt分析**:
```
故事原文内容：{{content}}

请从以上历史故事中提取最核心的主题，生成一个2个字的标题。

要求：
1. 必须是2个汉字
2. 要概括故事核心主题
3. 朗朗上口，有视觉冲击力
4. 例如：赤壁、长城、变法、征战等

直接输出2个字，不要其他解释。
```

**输出示例**: "赤壁"、"统一"、"变法"

---

### 3. 分镜处理阶段

#### Node 194566 - 输出节点（分镜提示）
**节点类型**: type: 13 (输出节点)  
**功能**: 显示正在创建视频分镜的提示  
**输出**: "正在创建视频分镜..."

---

#### Node 1165778 - 大模型_分镜
**节点类型**: type: 3 (LLM节点)  
**核心功能**: 将长文案分割成多个分镜段落  

**详细配置**:
```json
{
    "llmParam": {
        "modleName": "DeepSeek-V3",
        "modelType": 1738675210,
        "temperature": 0.8,
        "maxTokens": 8192,
        "responseFormat": 2
    }
}
```

**System Prompt详细分析**:
```
# 角色
你是一位专业的故事创意转化师，你能够深入理解故事文案的情节、人物、场景等元素，用生动且具体的语言为绘画创作提供清晰的指引。

## 技能
### 技能1： 生成分镜字幕
1. 当用户提供故事文案时，仔细分析文案中的关键情节、人物形象、场景特点等要素。
2. 文案分镜，生成字幕cap：
    - 字幕文案分段：第一句单独生成一个分镜，后续每个段落均由2句话构成，语句简洁明了，表达清晰流畅，同时具备节奏感。
    - 分割文案后特别注意前后文的关联性与一致性，必须与用户提供的原文完全一致，不得进行任何修改、删减。字幕文案必须严格按照用户给的文案拆分，不能修改提供的内容更不能删除内容

===回复示例===
[{
    "cap":"字幕文案"
}]
===示例结束===

## 限制:
- 只围绕用户提供的故事文案进行分镜绘画提示词生成和主题提炼，拒绝回答与该任务无关的话题。
- 所输出的内容必须条理清晰，分镜绘画提示词要尽可能详细描述画面，主题必须为2个字。 
- 视频文案及分镜描述必须保持一致。
- 输出内容必须严格按照给定的 JSON 格式进行组织，不得偏离框架要求。
- 只对用户提示的内容进行分镜，不能更改原文
- 严格检查输出的json格式正确性并进行修正，特别注意json格式不要少括号，逗号等
```

**分镜规则详解**:
1. **第一句独立**: 开头第一句单独成为一个分镜
2. **后续2句一组**: 之后每2句话组成一个分镜
3. **保持原文**: 不能修改任何原文内容
4. **JSON输出**: 严格的JSON格式输出

**输出示例**:
```json
[
  {"cap": "真的吗？一个小小的决定竟然改变了整个王朝的命运？"},
  {"cap": "你是春秋时期的一名普通士兵。此刻你站在城墙上，看着远方滚滚而来的烟尘。"},
  {"cap": "敌军的战鼓声震天响起，城内的百姓开始恐慌。你紧握手中的长矛，心跳如鼓。"}
]
```

---

#### Node 1578154 - 输出节点（提示词生成提示）
**节点类型**: type: 13 (输出节点)  
**功能**: 显示开始生成分镜画面提示词的提示  
**输出**: "开始生成分镜画面提示词.."

---

#### Node 186126 - 大模型_图像提示词
**节点类型**: type: 3 (LLM节点)  
**核心功能**: 为每个分镜生成详细的图像绘画提示词  

**详细配置**:
```json
{
    "llmParam": {
        "modleName": "DeepSeek-V3-0324",
        "modelType": 1742989917,
        "temperature": 1.0,
        "maxTokens": 16384,
        "responseFormat": 2
    }
}
```

**System Prompt深度分析**:
```
# 角色
根据分镜字幕cap生成绘画提示词desc_prompt。

## 技能
### 技能 1: 生成绘画提示
1. 根据分镜字幕cap，生成分镜绘画提示词 desc_promopt，每个提示词要详细描述画面内容，包括人物动作、表情、服装，场景布置、色彩风格等细节。
  - 风格要求：古代惊悚插画风格，颜色很深，黑暗中，黄昏，氛围凝重，庄严肃穆，构建出紧张氛围，古代服饰，古装，线条粗狂，清晰、人物特写，粗狂手笔，高清，高对比度，色彩低饱和，浅景深
  - 第一个分镜画面中不要出现人物，只需要一个画面背景

===回复示例===
[
  {
    "cap": "字幕文案",
    "desc_promopt": "分镜图像提示词"
  }
]
===示例结束===

## 限制:
- 只对用户提供的json内容补充desc_prompt字段，不能更改原文
- 严格检查输出的json格式正确性并进行修正，特别注意json格式不要少括号，逗号等
```

**视觉风格详细要求**:
- **画风**: 古代惊悚插画风格
- **光线**: 颜色很深，黑暗中，黄昏
- **氛围**: 凝重，庄严肃穆，紧张氛围  
- **服饰**: 古代服饰，古装
- **技法**: 线条粗狂，粗狂手笔
- **画质**: 清晰，高清，高对比度，色彩低饱和，浅景深
- **构图**: 人物特写
- **特殊要求**: 第一个分镜不出现人物，只要背景

**输出示例**:
```json
[
  {
    "cap": "真的吗？一个小小的决定竟然改变了整个王朝的命运？",
    "desc_promopt": "古代惊悚插画风格：黄昏时分的古代城池，城墙高耸，天空阴沉，乌云密布，颜色很深，黑暗中，氛围凝重，庄严肃穆，构建出紧张氛围，线条粗狂，清晰，高对比度，色彩低饱和，浅景深"
  },
  {
    "cap": "你是春秋时期的一名普通士兵。此刻你站在城墙上，看着远方滚滚而来的烟尘。",
    "desc_promopt": "古代惊悚插画风格：春秋时期士兵站在城墙上，身穿古代盔甲，手持长矛，表情紧张凝重，远方烟尘滚滚，战云密布，古代服饰，古装，线条粗狂，清晰，人物特写，粗狂手笔，高清，高对比度，色彩低饱和，浅景深"
  }
]
```

---

### 4. 媒体生成阶段

#### Node 1214309 - 输出节点（媒体生成提示）
**节点类型**: type: 13 (输出节点)  
**功能**: 显示开始生成视频配图的提示  
**输出**: "开始生成视频配图，请稍等.."

---

#### Node 121555 - 批处理节点
**节点类型**: type: 28 (批处理节点)  
**核心功能**: 批量并发处理多个场景的图像和音频生成  

**详细配置**:
```json
{
    "batchConfig": {
        "maxConcurrency": 3,
        "batchSize": 8,
        "inputSource": "scenes",
        "outputFields": ["image_list", "link_list", "duration_list"]
    }
}
```

**批处理逻辑**:
1. **输入**: scenes数组（包含cap和desc_promopt）
2. **并发数**: 最多3个场景同时处理
3. **处理流程**: 每个场景并发执行图像生成和语音合成
4. **输出**: 生成image_list、link_list、duration_list三个数组

**内部处理节点**:

##### 子节点: 图像生成分支

###### Node 131139 - 图像生成
**节点类型**: type: 16 (图像生成节点)  
**功能**: 根据描述提示词生成古代惊悚插画风格图片  

**详细配置**:
```json
{
    "modelSetting": {
        "model": 8,
        "ratio": 0,
        "custom_ratio": {"width": 1024, "height": 768},
        "ddim_steps": 40
    },
    "prompt": {
        "prompt": "古代惊悚插画风格：{{desc_promopt}}",
        "negative_prompt": ""
    }
}
```

**参数详解**:
- **模型**: model: 8 (特定的图像生成模型)
- **分辨率**: 1024x768 (4:3比例)
- **采样步数**: 40步 (高质量生成)
- **提示词模板**: "古代惊悚插画风格：{desc_promopt}"

###### Node 109484 - 智能优化图片提示词
**节点类型**: type: 4 (插件节点)  
**插件**: sd_better_prompt  
**功能**: 自动优化图像生成提示词，提高生成质量  

**插件配置**:
```json
{
    "pluginID": "sd_better_prompt",
    "inputParameters": [
        {"name": "prompt", "input": {"type": "string", "value": "{{desc_promopt}}"}}
    ]
}
```

**优化效果**:
- 原始: "古代战船在江面上"
- 优化后: "古代战船在江面上, ancient Chinese artistic style, atmospheric lighting, detailed illustration, high quality, masterpiece, 8k resolution..."

###### Node 1667619 - 图像生成_1（优化版本）
**节点类型**: type: 16 (图像生成节点)  
**功能**: 使用优化后的提示词重新生成图像  

**配置**: 与Node 131139相同，但使用优化后的提示词

###### Node 133787 - 选择器节点
**节点类型**: type: 8 (条件选择器)  
**功能**: 根据条件选择使用哪个图像生成结果  

**选择逻辑**:
```javascript
// 伪代码
if (optimized_image && optimized_image.quality > original_image.quality) {
    return optimized_image;
} else {
    return original_image;
}
```

###### Node 187299 - 图像合并代码节点
**节点类型**: type: 5 (代码节点)  
**功能**: 合并两个图像生成结果，优先使用第一个成功的  

**代码逻辑**:
```javascript
async function main({ params }: Args): Promise<Output> {
    const { image1, image2 } = params;
    
    // 优先使用第一个图像
    if (image1 && image1.url) {
        return { image_url: image1.url };
    }
    
    // 降级使用第二个图像
    if (image2 && image2.url) {
        return { image_url: image2.url };
    }
    
    throw new Error("Both image generation failed");
}
```

##### 子节点: 语音合成分支

###### Node 182040 - 音色与文本合成音频
**节点类型**: type: 4 (插件节点)  
**插件**: speech_synthesis  
**功能**: 将分镜字幕转换为语音  

**详细配置**:
```json
{
    "pluginID": "speech_synthesis",
    "inputParameters": [
        {"name": "text", "input": {"type": "string", "value": "{{cap}}"}},
        {"name": "voice_id", "input": {"type": "string", "value": "7468512265134932019"}},
        {"name": "speed", "input": {"type": "float", "value": 1.2}},
        {"name": "volume", "input": {"type": "float", "value": 1.0}}
    ]
}
```

**语音参数详解**:
- **音色ID**: 7468512265134932019 (悬疑解说音色)
- **语速**: 1.2倍速 (略快于正常语速)
- **音量**: 1.0 (标准音量)
- **输出格式**: MP3格式音频文件

###### Node 178228 - 音频时长计算节点
**节点类型**: type: 5 (代码节点)  
**功能**: 计算生成音频的时长（微秒）  

**代码逻辑**:
```javascript
async function main({ params }: Args): Promise<Output> {
    const { audio_url } = params;
    
    // 通过API获取音频时长
    const duration = await getAudioDuration(audio_url);
    
    // 转换为微秒
    const durationMicroseconds = Math.floor(duration * 1000000);
    
    return { duration: durationMicroseconds };
}
```

---

### 5. 主角图像生成分支

#### Node 1301843 - 大模型_主角首图
**节点类型**: type: 3 (LLM节点)  
**功能**: 分析故事内容生成主角形象描述  

**详细配置**:
```json
{
    "llmParam": {
        "modleName": "DeepSeek-V3",
        "modelType": 1738675210,
        "temperature": 0.8,
        "maxTokens": 8192,
        "responseFormat": 2
    }
}
```

**System Prompt分析**:
```
# 角色
根据故事信息生成故事主角开场绘画提示词desc_prompt。

## 技能
### 技能 1: 生成绘画提示
1. 根据故事信息，生成主角人物绘画提示词 desc_promopt，详细描述人物动作、表情、服装，色彩风格等细节。
  - 风格要求：古代惊悚插画风格，背景留白，颜色昏暗，黑暗中，黄昏，氛围凝重，庄严肃穆，构建出紧张氛围，古代服饰，古装，线条粗狂，清晰、人物特写，粗狂手笔，高清，高对比度，色彩低饱和，浅景深
  - 画面只需要出现一个人物，背景留白
  - 人物需正对屏幕，人物在画面正中间

# 限制
1. 只输出绘画提示词，不要输出其他额外内容
```

**主角图像要求**:
- **人物数量**: 只出现一个人物
- **背景**: 背景留白
- **构图**: 正对屏幕，人物居中
- **风格**: 与场景图一致的古代惊悚插画风格

---

#### Node 1866199 - 图像生成_主角首图
**节点类型**: type: 16 (图像生成节点)  
**功能**: 根据主角描述生成人物图像  

**配置**: 与场景图像生成节点相同

---

#### Node 170966 - 抠图节点
**节点类型**: type: 4 (插件节点)  
**插件**: cutout  
**功能**: 将主角图像抠图，生成透明背景PNG  

**详细配置**:
```json
{
    "pluginID": "cutout",
    "apiName": "cutout",
    "inputParameters": [
        {"name": "url", "input": {"type": "image", "value": "{{主角图像URL}}"}},
        {"name": "only_mask", "input": {"type": "string", "value": "0"}},
        {"name": "output_mode", "input": {"type": "string", "value": "0"}}
    ]
}
```

**抠图参数**:
- **only_mask**: "0" (返回抠图结果尺寸)
- **output_mode**: "0" (透明背景图模式)
- **输出**: 透明背景PNG格式的主角图像

---

### 6. 数据整合阶段

#### Node 163547 - 代码节点（数据整合）
**节点类型**: type: 5 (代码节点)  
**核心功能**: 整合所有媒体数据，构建时间轴，处理字幕分割  

**输入数据**:
- image_list: 场景图像URL数组
- audio_list: 音频URL数组  
- duration_list: 音频时长数组（微秒）
- scenes: 场景数据（字幕+提示词）
- title: 2字标题
- role_img_url: 主角透明背景图像

**核心处理逻辑**:

##### 1. 音频时间轴构建
```javascript
const audioData = [];
let audioStartTime = 0;

for (let i = 0; i < audio_list.length && i < duration_list.length; i++) {
    const duration = duration_list[i];
    audioData.push({
        audio_url: audio_list[i],
        duration,
        start: audioStartTime,
        end: audioStartTime + duration
    });
    audioStartTime += duration;
}
```

##### 2. 图像动画配置
```javascript
const imageData = [];

for (let i = 0; i < audio_list.length && i < duration_list.length; i++) {
    const duration = duration_list[i];
    
    // 奇偶交替动画效果
    if((i-1)%2==0) {
        imageData.push({
            image_url: image_list[i],
            start: audioStartTime,
            end: audioStartTime + duration,
            width: 1440,
            height: 1080,
            in_animation: "轻微放大",
            in_animation_duration: 100000
        });
    } else {
        imageData.push({
            image_url: image_list[i],
            start: audioStartTime,
            end: audioStartTime + duration,
            width: 1440,
            height: 1080
        });
    }
}
```

##### 3. 主角图像配置
```javascript
const roleImgData = [{
    image_url: params.role_img_url,
    start: 0,
    end: duration_list[0],  // 只在第一段显示
    width: 1440,
    height: 1080
}];
```

##### 4. 智能字幕分割系统
```javascript
const SUB_CONFIG = {
    MAX_LINE_LENGTH: 25,  // 最大字符数
    SPLIT_PRIORITY: ['。','！','？','，',',','：',':','、','；',';',' '], // 分割优先级
    TIME_PRECISION: 3
};

function splitLongPhrase(text, maxLen) {
    if (text.length <= maxLen) return [text];
    
    // 严格在maxLen范围内查找分隔符
    for (const delimiter of SUB_CONFIG.SPLIT_PRIORITY) {
        const pos = text.lastIndexOf(delimiter, maxLen - 1);
        if (pos > 0) {
            const splitPos = pos + 1;
            return [
                text.substring(0, splitPos).trim(),
                ...splitLongPhrase(text.substring(splitPos).trim(), maxLen)
            ];
        }
    }
    
    // 汉字边界检查防止越界
    const startPos = Math.min(maxLen, text.length) - 1;
    for (let i = startPos; i > 0; i--) {
        if (/[\p{Unified_Ideograph}]/u.test(text[i])) {
            return [
                text.substring(0, i + 1).trim(),
                ...splitLongPhrase(text.substring(i + 1).trim(), maxLen)
            ];
        }
    }
    
    // 强制分割
    const splitPos = Math.min(maxLen, text.length);
    return [
        text.substring(0, splitPos).trim(),
        ...splitLongPhrase(text.substring(splitPos).trim(), maxLen)
    ];
}
```

##### 5. 时间轴精确计算
```javascript
const processSubtitles = (captions, subtitleDurations) => {
    let processedSubtitles = [];
    let processedSubtitleDurations = [];
    
    captions.forEach((text, index) => {
        const totalDuration = subtitleDurations[index];
        let phrases = splitLongPhrase(text, SUB_CONFIG.MAX_LINE_LENGTH);
        
        // 清理标点符号
        phrases = phrases.map(p => p.replace(cleanRegex, '').trim())
                       .filter(p => p.length > 0);
        
        const totalChars = phrases.reduce((sum, p) => sum + p.length, 0);
        let accumulatedμs = 0;
        
        phrases.forEach((phrase, i) => {
            const ratio = phrase.length / totalChars;
            let durationμs = i === phrases.length - 1 
                ? totalDuration - accumulatedμs
                : Math.round(totalDuration * ratio);
            
            processedSubtitles.push(phrase);
            processedSubtitleDurations.push(durationμs);
            accumulatedμs += durationμs;
        });
    });
    
    // 生成时间轴
    const textTimelines = [];
    let currentTime = 0;
    
    processedSubtitleDurations.forEach(durationμs => {
        textTimelines.push({
            start: currentTime,
            end: currentTime + durationμs
        });
        currentTime += durationμs;
    });
    
    return { textTimelines, processedSubtitles };
};
```

##### 6. 音效配置
```javascript
// 开场音效（4.88秒）
const kc_audio_url = "故事开场音效.MP3";
const kc_audio_data = [{
    audio_url: kc_audio_url,
    duration: 4884897,  // 微秒
    start: 0,
    end: 4884897
}];

// 背景音乐（全程）
const bg_audio_url = "故事背景音乐.MP3";
const bg_audio_data = [{
    audio_url: bg_audio_url,
    duration: maxDuration,
    start: 0,
    end: maxDuration
}];
```

**输出数据结构**:
```javascript
const ret = {
    "audioData": JSON.stringify(audioData),           // 配音轨道数据
    "bgAudioData": JSON.stringify(bg_audio_data),     // 背景音乐数据
    "kcAudioData": JSON.stringify(kc_audio_data),     // 开场音效数据
    "imageData": JSON.stringify(imageData),           // 场景图像数据
    "text_timielines": textTimelines,                 // 字幕时间轴
    "text_captions": processedSubtitles,              // 处理后字幕
    "title_list": title_list,                         // 标题文字
    "title_timelimes": title_timelimes,              // 标题时间轴
    "roleImgData": JSON.stringify(roleImgData)        // 主角图像数据
};
```

---

### 7. 视频合成阶段

#### Node 106358 - 输出节点（视频编排提示）
**节点类型**: type: 13 (输出节点)  
**功能**: 显示视频编排进度提示  
**输出**: "视频编排中，即将完成..."

---

#### Node 168118 - 创建草稿
**节点类型**: type: 4 (插件节点)  
**插件**: 视频合成_剪映小助手:create_draft  
**功能**: 创建剪映视频草稿项目  

**详细配置**:
```json
{
    "pluginID": "7457837925833801768",
    "apiName": "create_draft",
    "inputParameters": [
        {"name": "height", "input": {"type": "integer", "value": 1080}},
        {"name": "width", "input": {"type": "integer", "value": 1440}},
        {"name": "user_id", "input": {"type": "integer", "value": 1262}}
    ]
}
```

**输出**: draft_url (草稿链接)

---

#### Node 125268 - 批量添加音频（配音）
**节点类型**: type: 4 (插件节点)  
**插件**: 视频合成_剪映小助手:add_audios  
**功能**: 将配音音频添加到草稿项目  

**输入数据**: audioData (JSON格式的音频信息数组)
**数据结构**:
```json
[
  {
    "audio_url": "配音音频URL",
    "duration": 5000000,
    "start": 0,
    "end": 5000000
  }
]
```

---

#### Node 109941 - 批量添加图片（场景图）
**节点类型**: type: 4 (插件节点)  
**插件**: 视频合成_剪映小助手:add_images  
**功能**: 将场景图片添加到草稿项目  

**详细配置**:
```json
{
    "inputParameters": [
        {"name": "draft_url", "input": "草稿链接"},
        {"name": "image_infos", "input": "图像数据JSON"},
        {"name": "scale_x", "input": {"type": "float", "value": 1.0}},
        {"name": "scale_y", "input": {"type": "float", "value": 1.0}}
    ]
}
```

**图像数据结构**:
```json
[
  {
    "image_url": "场景图片URL",
    "start": 0,
    "end": 5000000,
    "width": 1440,
    "height": 1080,
    "in_animation": "轻微放大",
    "in_animation_duration": 100000
  }
]
```

---

#### Node 1087428 - 批量添加图片（主角首图）
**节点类型**: type: 4 (插件节点)  
**插件**: 视频合成_剪映小助手:add_images  
**功能**: 将主角透明背景图添加到草稿项目  

**配置**:
```json
{
    "inputParameters": [
        {"name": "image_infos", "input": "roleImgData"},
        {"name": "scale_x", "input": {"type": "float", "value": 2.0}},
        {"name": "scale_y", "input": {"type": "float", "value": 2.0}}
    ]
}
```

**特殊配置**: 主角图像放大2倍显示

---

#### Node 1114402 - 批量添加音频（开场音效）
**节点类型**: type: 4 (插件节点)  
**功能**: 添加开场音效到草稿项目  
**输入**: kcAudioData (开场音效数据)

---

#### Node 1190196 - 批量添加音频（背景音乐）
**节点类型**: type: 4 (插件节点)  
**功能**: 添加背景音乐到草稿项目  
**输入**: bgAudioData (背景音乐数据)

---

### 8. 关键帧动画系统

#### Node 120984 - 代码_关键帧
**节点类型**: type: 5 (代码节点)  
**功能**: 生成图像缩放关键帧动画配置  

**详细算法**:
```python
async def main(args: Args) -> Output:
    params = args.params
    segment_ids = params['segment_ids']        # 图像片段ID
    times = params['duration_list']           # 时长数组
    seg = params['segment_infos']             # 片段信息
    
    keyframes = []
    
    for idx, seg_id in enumerate(segment_ids):
        if idx == 0:  # 跳过第一张图片（主角图）
            continue
        
        audio_duration = int(float(times[idx]))
        
        # 奇偶交替缩放方向
        cycle_idx = idx - 1
        if cycle_idx % 2 == 0:  # 偶数：1.0 -> 1.5
            start_scale = 1.0
            end_scale = 1.5
        else:  # 奇数：1.5 -> 1.0
            start_scale = 1.5
            end_scale = 1.0
        
        # 起始关键帧
        keyframes.append({
            "offset": 0,
            "property": "UNIFORM_SCALE",
            "segment_id": seg_id,
            "value": start_scale,
            "easing": "linear"
        })
        
        # 结束关键帧
        keyframes.append({
            "offset": audio_duration,
            "property": "UNIFORM_SCALE", 
            "segment_id": seg_id,
            "value": end_scale,
            "easing": "linear"
        })
    
    # 主角图像特殊动画（2.0 -> 1.2 -> 1.0）
    keyframes.append({
        "offset": 0,
        "property": "UNIFORM_SCALE",
        "segment_id": seg[0]['id'],
        "value": 2.0,
        "easing": "linear"
    })
    
    keyframes.append({
        "offset": 533333,  # 0.533秒
        "property": "UNIFORM_SCALE",
        "segment_id": seg[0]['id'],
        "value": 1.2,
        "easing": "linear"
    })
    
    keyframes.append({
        "offset": seg[0]['end'] - seg[0]['start'],
        "property": "UNIFORM_SCALE",
        "segment_id": seg[0]['id'],
        "value": 1.0,
        "easing": "linear"
    })
    
    return {"keyFrames": json.dumps(keyframes)}
```

**动画效果分析**:
- **场景图**: 奇偶交替的1.0↔1.5缩放循环
- **主角图**: 2.0→1.2→1.0的开场动画
- **缓动**: 线性缓动
- **同步**: 与音频时长精确同步

---

#### Node 146723 - 添加关键帧
**节点类型**: type: 4 (插件节点)  
**插件**: 视频合成_剪映小助手:add_keyframes  
**功能**: 将关键帧动画应用到草稿项目  

**输入**: keyframes (JSON格式的关键帧数据)

---

### 9. 字幕系统

#### 主字幕分支

##### Node 180947 - 字幕数据生成器
**节点类型**: type: 4 (插件节点)  
**插件**: 剪映小助手数据生成器:caption_infos  
**功能**: 根据字幕文本和时间轴生成字幕数据  

**输入**:
- texts: 处理后的字幕文本数组
- timelines: 字幕时间轴数组

**输出**: 符合剪映格式的字幕数据JSON

##### Node 158201 - 批量字幕
**节点类型**: type: 4 (插件节点)  
**插件**: 视频合成_剪映小助手:add_captions  
**功能**: 将主字幕添加到草稿项目  

**详细配置**:
```json
{
    "inputParameters": [
        {"name": "captions", "input": "字幕数据"},
        {"name": "alignment", "input": {"type": "integer", "value": 1}},    // 居中对齐
        {"name": "border_color", "input": {"type": "string", "value": "#000000"}},  // 黑色边框
        {"name": "font_size", "input": {"type": "integer", "value": 7}},           // 7号字体
        {"name": "text_color", "input": {"type": "string", "value": "#FFFFFF"}},   // 白色文字
        {"name": "transform_x", "input": {"type": "float", "value": 0}},           // 水平居中
        {"name": "transform_y", "input": {"type": "float", "value": -810}}         // 垂直偏移
    ]
}
```

#### 标题字幕分支

##### Node 1204256 - 字幕_标题2个字
**节点类型**: type: 4 (插件节点)  
**功能**: 生成开场2字标题的字幕数据  

**输入**:
- texts: 2字标题文本
- timelines: 标题显示时间轴
- in_animation: "弹入" (入场动画)
- keyword_color: "red" (关键词颜色)
- keyword_font_size: 60 (标题字号)

##### Node 1182713 - 字幕_开场2个字
**节点类型**: type: 4 (插件节点)  
**功能**: 将标题字幕添加到草稿项目  

**详细配置**:
```json
{
    "inputParameters": [
        {"name": "alignment", "input": {"type": "integer", "value": 1}},          // 居中对齐
        {"name": "border_color", "input": {"type": "string", "value": "#ffffff"}}, // 白色边框
        {"name": "font", "input": {"type": "string", "value": "书南体"}},         // 书南体字体
        {"name": "font_size", "input": {"type": "integer", "value": 40}},         // 40号字体
        {"name": "letter_spacing", "input": {"type": "float", "value": 26}},      // 26像素字间距
        {"name": "text_color", "input": {"type": "string", "value": "#000000"}},  // 黑色文字
        {"name": "transform_x", "input": {"type": "float", "value": 0}},          // 水平居中
        {"name": "transform_y", "input": {"type": "float", "value": 0}}           // 垂直居中
    ]
}
```

---

### 10. 最终输出阶段

#### Node 104782 - 保存草稿
**节点类型**: type: 4 (插件节点)  
**插件**: 视频合成_剪映小助手:save_draft  
**功能**: 保存完整的剪映草稿项目  

**配置**:
```json
{
    "inputParameters": [
        {"name": "draft_url", "input": "草稿链接"},
        {"name": "user_id", "input": {"type": "integer", "value": 1262}}
    ]
}
```

---

#### Node 904077 - 输出_5（最终结果）
**节点类型**: type: 13 (输出节点)  
**功能**: 输出最终的草稿地址  

**输出模板**:
```
视频草稿地址，请使用剪映小助手下载：
{{draft_url}}
```

---

## 工作流执行顺序分析

### 执行依赖关系图

```
用户输入主题
    ↓
142052(开始提示) → 121343(文案生成) ─┬─→ 1199098(主题提取) → 163547(数据整合)
                                    │                              ↑
                                    ├─→ 1165778(分镜) → 186126(图像提示词)
                                    │            ↓                 ↑
                                    │    121555(批处理) ────────────┤
                                    │            ↓                 ↑
                                    └─→ 1301843(主角描述) → 1866199(主角生成) → 170966(抠图)
                                                                               ↓
163547(数据整合) → 168118(创建草稿) → 多个并行轨道添加 → 146723(关键帧) → 字幕系统 → 104782(保存) → 904077(输出)
```

### 并行处理节点

1. **批处理内部并行**:
   - 图像生成 (131139)
   - 提示词优化 (109484) 
   - 优化图像生成 (1667619)
   - 语音合成 (182040)
   - 时长计算 (178228)

2. **主角图像并行**:
   - 主角描述生成 (1301843)
   - 主角图像生成 (1866199) 
   - 抠图处理 (170966)

3. **视频轨道并行添加**:
   - 配音轨道 (125268)
   - 场景图像轨道 (109941)
   - 主角图像轨道 (1087428)
   - 背景音乐轨道 (1190196)
   - 开场音效轨道 (1114402)

4. **字幕系统并行**:
   - 主字幕处理 (180947 → 158201)
   - 标题字幕处理 (1204256 → 1182713)

---

## 关键技术细节

### 1. 时间轴精度控制
- **单位**: 微秒 (μs)
- **精度**: 整数微秒级别
- **同步**: 音频、图像、字幕完全同步

### 2. 动画缓动算法
- **类型**: 线性缓动 (linear)
- **属性**: UNIFORM_SCALE (等比缩放)
- **模式**: 奇偶交替循环

### 3. 字幕智能分割
- **最大长度**: 25字符
- **分割优先级**: 句号 > 感叹号 > 问号 > 逗号...
- **边界保护**: 汉字完整性检查

### 4. 批处理控制
- **最大并发**: 3个场景
- **失败处理**: 自动降级和重试
- **资源管理**: 内存和API调用优化

这个详细分析涵盖了工作流中每个节点的具体功能、配置参数、处理逻辑和输出格式，为后续的Python实现提供了完整的技术规范。