"""
多语言文案生成器 - 基于DeepSeek-V3的历史故事文案生成
对应原工作流Node_121343配置
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

from core.config_manager import ConfigManager, ModelConfig
# 缓存已删除
from utils.file_manager import FileManager
from utils.enhanced_llm_manager import EnhancedLLMManager

@dataclass
class ScriptGenerationRequest:
    """文案生成请求"""
    theme: str                  # 主题
    language: str              # 语言代码 (zh, en, es)
    style: str = "horror"      # 风格：horror, documentary, dramatic
    target_length: int = 1000  # 目标长度（字符数）
    include_title: bool = True # 是否包含标题

@dataclass  
class GeneratedScript:
    """生成的文案"""
    title: str                 # 标题
    content: str               # 正文内容
    language: str              # 语言
    theme: str                 # 主题
    word_count: int            # 字数统计
    generation_time: float     # 生成耗时
    model_used: str            # 使用的模型

class ScriptGenerator:
    """
    多语言文案生成器
    
    基于原Coze工作流Node_121343配置：
    - 模型: DeepSeek-V3
    - Temperature: 0.8  
    - Max tokens: 1024
    - 支持多语言：中文、英语、西班牙语
    """
    
    def __init__(self, config_manager: ConfigManager, 
                 file_manager: FileManager):
        self.config = config_manager
        self.file_manager = file_manager
        self.logger = logging.getLogger('story_generator.content')
        
        # 支持的语言 - 必须在加载提示词模板之前设置
        self.supported_languages = self.config.get_supported_languages()
        
        # 获取LLM配置
        self.llm_config = self.config.get_llm_config('script_generation')
        
        # 初始化多提供商LLM客户端管理器
        self.llm_manager = EnhancedLLMManager(config_manager)
        self.logger.info("✅ 使用增强LLM管理器 (统一架构)")
        
        # 加载提示词模板
        self._load_prompt_templates()
    
    
    def _load_prompt_templates(self):
        """加载提示词模板"""
        self.prompt_templates = {}
        prompts_dir = Path("config/prompts")
        
        for lang in self.supported_languages:
            lang_dir = prompts_dir / lang
            if lang_dir.exists():
                # 加载文案生成提示词
                script_prompt_file = lang_dir / "script_generation.txt"
                if script_prompt_file.exists():
                    try:
                        content = self.file_manager.load_text(script_prompt_file)
                        if content:
                            self.prompt_templates[lang] = content
                            self.logger.debug(f"Loaded script prompt for language: {lang}")
                    except Exception as e:
                        self.logger.error(f"Failed to load script prompt for {lang}: {e}")
        
        if not self.prompt_templates:
            self.logger.warning("No script generation prompts loaded, using default templates")
            self._create_default_prompts()
    
    def _create_default_prompts(self):
        """创建默认提示词模板"""
        self.prompt_templates = {
            'zh': """请根据用户提供的【主题】，按照以下结构生成一段历史类短视频口播文案：

1. **悬念开场**：以"【朝代/场景】+ 反常识疑问/断言"开篇，激发观众兴趣（例："古代【某职业】真的比【对比对象】更【形容词】吗？"）。
2. **身份代入**：用第二人称"你"描述主角身份、时代背景及面临的致命危机（需包含具体官职/处境/对手），不要出现"想象一下"等过渡词，直接进入主题。
3. **冲突升级**：
   - 第一层：外部压力（如敌军压境、上级压迫、天灾降临）
   - 第二层：内部瓦解（如下属背叛、资源短缺、疾病蔓延）
   - 第三层：道德困境（如忠义两难、屠城抉择、政斗站队）
4. **破局细节**：主角采取3个递进动作，包含：
   - 震慑手段（当众处决/焚毁证据）
   - 心理博弈（离间计/匿名信）
   - 终极底牌（隐藏密件/借势压人）
5. **主题收尾**：通过主角结局（惨胜/悲壮失败）引出金句，揭示历史规律（如"权力本质/战争真相/人性弱点"）。

**要求**：
- 每段不超过3句话，多用短句制造紧张节奏
- 加入至少2处历史专业术语
- 在关键转折点使用感官描写（气味/触感/视觉冲击）
- 结尾以"这一刻你终于明白…"句式点题
- 生成1000字左右口播文案
- 文案由长短句构成，遇到长句会用逗号分隔成短句，每个短句不能超过19个汉字

**参考文案**：
参考文案1：
在古代，当一个七品县令真的比做皇帝还爽吗？你是一个七品县令，听着像是芝麻官，实际上却管着一线生杀。你到任第一天，文案积压，吏园散漫，商人压税，盗匪频繁，所有人都在盯着你，想看看你这个读书人究竟能撑几日。于是，你命人将城中四大银行、三大米商召来，说了一句话，自今日起，税从清征，人从严制，谁敢藏奸瞒骗，先抄家，再杀头。众人皆笑，你却不恼，只是冷冷记下每人姓名，派人查账。三日后，你当街砍了一个米商账房，把人头挂在城门口。不久，其余几家主动上门认错，乖乖交税送礼，百姓自此称你为顾青天。你从不自称清官，但你知道，在这地方，拳头和律法并重才叫威望。一个月后，你已经在县城里站稳了脚跟。天还未亮，衙门门口已跪满人。左边是乡绅土豪求你叛帝，右边是盐商粮商给你送礼，你打了个哈欠。走出卧房后堂，十几名婢女簇拥着为你更衣梳发。你才刚坐下，茶就端来了，不是普通茶，是百里外送来的贡品。龙井三千银子一斤，一口下去，香气绕喉。你懒洋洋的抬眼看着堂下跪着的众人，手一挥，先问田地安，其余让他们在外等着。话音未落，师爷立刻应声，堂上传来惊堂木声，升堂在云阳县，穷人看你是神，富人把你当祖宗，就连知府大人来视察，都得先送一船好酒，再送一个歌妓，才敢上门拜访。你笑着收下他来视茶，你派人抬着软轿出城，五里相迎，不是给她面子，而是要让他知道，你虽然是七品，但这云阳县早已是你的天下。你升任第三年的秋天，县衙后库突发火灾，你亲自查探火因，结果意外发现一批私盐帐簿署名竟是你手下最信任的书立李记。你震怒，立即将其缉拿，却在其家中搜出一封未寄出的密信，写明这批私言背后勾结知州卢大人，牵连州府多名官员。你这才意识到，你触碰了这片土地上最不能动的那条线。延说，第二天你才刚出堂，就有人呈上一封匿名举报信，连你的私房收礼记录都一应俱全。你第一次感到这不是污蔑，这是操盘已久的杀局。知州大人紧急来访，私下告诫你有人要动，你背后牵的是京城兵部与阎道衙门，你得自己找活路。你立刻封锁案卷，亲自入库查账，发现那些伪账本竟源自你手下最信任的书立。你将其关入大牢，一审才知他的妻儿被人挟持，只得从命栽赃你，你这才意识到，自己就是那块要被剃掉的棋子。第二日，你还未来得及申辩，便接到了停职审查的诏书。知州亲率提其封了你的书房后堂暗牍，你如过街老鼠，众人避之。你低头无语，却没有认输，跟你早有后手。你连夜写密折命心腹快马送至京中清流大臣门下，可三日后却传来噩耗，送信之人马踏山崖，尸骨无存。此刻，你彻底陷入死局，这时钦差已入陷，兵部主事钦来查办，你被软禁在后堂，你以为你的结局将与前任三位县令无异，都死于意外。正当你思索破局之法时，昔日曾受你父亲庇护的朝中高官命书立偷偷送来一封信，信里竟藏着一张对账残页，印有兵部大员亲笔落款与黑岩交易详情。你明白了？他们大意了。栽赃太快，忘了悔证。7日后，钦差升堂审你。你披发跪堂，血衣染袍，众人以为你彻底崩溃了，你却突然从怀中掏出那张残页，当众高喊，我顾怀珍，问心无愧。今日一命换一局，看天子信谁。钦差当场变色，百姓哗然。而你早已让人将密政副本藏匿。一旦你死，城门口便贴文告公示。这一次，他们不敢动你。钦差低头退堂，3日后急返京城，再五日，圣旨亲临。顾怀贞未曾贪墨，实为中职之臣，留任云阳县专责清查南沿岸。你身披旧袍，眼中血丝未退，但腰杆挺直如初。你看着天轻声念叨我顾怀珍，就算是七品芝麻官，也能让权臣避让百官低头。那些试图吞下你的权贵，一个个被抄家砍头，这回你虽然没有升官，但却赢得了天下最难赢的那一局。

参考文案2：
一个汉朝使者竟在敌国当众砍了国王的人头，却没人敢多说一句话。今天我们讲大汉最狂使者班超，你是一名大汉边疆的普通士兵，略懂一些西域语言。这天长官班超突然发话，你准备一下，后天随我出使西域。你心头一紧，西域远在万里，危险重重，去过的使者几乎全都被砍了。可班超的眼神告诉你，这个任务不容你拒绝，行进的路程异常艰难，漫天风沙遮蔽了天际。一路上，你多次冒出逃跑的念头，可李智告诉你，脱离了大部队也是死路一条。三个月后，你们终于抵达了第一站楼兰。你早已听说过这里的危险，楼兰国王血腥手段让无数使者丧命于此。大殿内，楼兰国王坐在王座上冷眼看着你们周围的侍卫目露凶光，气氛紧张的让你几乎无法呼吸。你担心班超要是说错话会连累大伙被处死，不料他毫不畏惧的走上前，直指国王的鼻子，怒骂道，你这背信弃义的狗东西竟敢欺骗盟友匈奴使团从你这经过，竟然不告诉老子怎么是不是翅膀硬了？说完，班超看向你，冷声道，翻译给他听。你心头猛然一惊，差点喷出一口老血，但还是战战兢兢的翻译给国王听。国王怒吼道，你信不信我现在就砍了你。然而令你意想不到的是，班超不但没有害怕，反而把脖子凑了上去，挑衅道，来来来，朝这里砍不砍你是我孙子。此话一出，你被惊得愣在了原地，冷汗浸湿了三层衣袍，只听班超继续说道，南越杀我汉使，九郡被夷为平地，大碗杀我汉室，国王的脑袋被挂在城门上。今日你若杀我，明日汉军便会举国而出，屠径你楼兰数辈，而我的子孙会受到封赏，我也会名留青史，老子求之不得。你站在旁边心跳如雷鼓，仿佛下一刻就会被拖出去斩首，但令人惊讶的是，楼兰国王非但没有下令砍了你们，竟然还低头认错，表示愿意重新恢复大汉。一时间你被震惊的愣在了原地，我大汉朝啥时候那么硬气了？在别人的地盘上训斥他们的国王，如同老子训斥儿子一样。但更令你惊掉下巴的事还在后头，你们继续前行，来到了善善国。国王的礼遇让你觉得这一次可能是个顺利的任务。然而随着几天的相处，你渐渐察觉到不对劲，善善国王的态度开始变得冷淡，班超肯定也察觉到了这一点，过了几天，他把善善王的亲信叫了过来，语气平静却像刀匈奴的使者来了吧，打算待几天。一句话把对方吓得脸色发白，哆嗦着回道，五六日，你惊愕的看着班超，他没有直接询问匈奴使者是否到来，而是问得极其巧妙，仿佛早已知道一切。你心里发凉，36个人被困异国，如果善善国王决定投靠匈奴，你们所有人都将命丧于此，成为他的投名状。夜晚寒风凛冽，班超召集弟兄们喝酒。酒过三巡，他忽的一拍桌子，兄弟们，我们被困异国，国王已变脸，说不定哪天就把我们绑了送给匈奴。我们死在这，不会有墓碑，不会有人记得。如今这局面，你们说该怎么办？有人先喊了一句，无论是死是生，我们都听你的。接着你们36人齐声应下班超点头，冷静的不像是要杀人的将军，更像个写好了剧本的导演。我去匈奴营上放火，你们埋伏在出口，火势一起，谁跑出来就砍谁，谁敢逃就射谁。深夜风大如刀，班超点燃火把扔进匈奴使者的驻地。火光腾起那一刻，你心跳几乎停了，敌人惊慌出逃，你们早已守在四周，一刀一个。惨叫声4起，匈奴使节头颅飞溅，愚者被活活烧死。次日一早，班超提着一颗焦黑的脑袋，亲自去见善善国王。你跟在他身后，手还在发抖，只见他将人头扔在国王前，冷声道，既然你犹犹豫豫，那老子就替你做个决断，投靠谁国，自己看着办。国王脸色煞白，当即俯首称臣。不久后，单善国归附，震动西域。你实在忍不住轻声问他，我们这样是不是太霸道了？班超没回头，只是眉头一皱。他们弱却不谦卑，贪却不识相。你给他们脸，他们觉得你好欺负。你不拔刀，他们就敢骑在你头上拉屎。接下来的日子里，班超带你们在西域各国大闹一通后，还是不满意，因为这些国家只是迫于压力，表面沉浮。日后一有机会，他们还是会反水。于是他主动向霍光大将军请命，说要干一票大的。霍光大将军听了只淡淡一笑，不错，可以先拿楼兰国王来练练手。你听到这话，整个人僵在原地。练手？你们才多少人？三十几人而已，要去杀一个国王，颠覆一个政权，这不是练手，是送命啊。但你看看班超，他脸上没有一丝犹豫，你开始害怕，甚至比第一次跟他出使还要紧张。但你心里也清楚，一旦你们失败，大汉铁骑必定杀回来，到时候敌国血流成河，而你将作为烈士。这一次，你们带了满车金银，说是天子赏赐，与楼兰国君重修就好。小小楼兰国王见到这些宝物，两眼都直了，笑得比狗还谄媚，酒也越喝越猛，话也越说越飘。班超看向你只是一个眼神，你立刻明白，你悄悄带着另一个兄弟绕到屏风后等候。他走到国王耳边低语，天子密令，需要私下传话。楼兰王晃晃悠悠站起，毫无防备的走向你们。你屏住呼吸，手紧握剑柄，他刚一露头，班超眼中寒光一闪，剑刃贯穿心口。楼兰王连叫都没叫出声，瞪着一双死不瞑目的眼瘫软倒地。屏风外的文武百官当场傻眼，气氛一瞬间炸裂，有人握住了刀柄，有人咬牙低吼，啪板朝一声怒喝，酒被应声砸碎，谁若敢动，老子灭了你楼兰。小波一字一句像从地狱里拉出的声音，你也不知道他们到底怕了谁，怕班超，怕你们，还是怕背后那个庞然大物大汉。总之，他们全傻了，一个个低着头，连呼吸都小心翼翼。你们就这么砍下国王头颅，从人群中走出去，没有人拦，没有人动，你仿佛看见了卫青的铠甲，霍去病的战马，汉武帝的目光，还有那压在整个西域上空的大汉铁骑。你走得越来越稳，步子越来越大，头颅越抬越高，体梁越挺越直。这一刻你真切的为自己身为一个大汉子民而骄傲。

参考文案3：
古代战场上的瘟疫真的比敌人的刀剑更可怕吗？你是一名普通的宋朝士兵，此刻正坚守着一座即将被金军攻破的城池。就在敌军将要爬上城楼之际，你冒死将一架攻程梯狠狠推翻，鲜血混杂着汗水滴落在你的盔甲上，数日的厮杀抵抗使你浑身疼痛，但你依旧拼尽全力。终于熬到了半夜，敌军的攻势退去，你扶着刀柄浑身颤抖。原以为熬过了这一波攻势便能稍作喘息，却不知更可怕的敌人早已悄然逼近。午时3刻，你正趴在墙角休息，突然一具尸体从空中坠落，重重的砸在你脚边，顿时间血浆4溅。只见城外敌军竟然将死去士兵的尸体绑在投石车上，纷纷投入你们驻守的城中。尸体在半空中划过一道诡异的弧线，砸落在城内的街道上，散发出阵阵恶臭。你站在城墙上满心疑惑的看着这一幕，城中士兵甚至好奇的凑近尸体观察，却未料到一场灾难正在悄悄蔓延。夜幕降临，营地里弥漫着诡异的寂静。你窝在狭窄潮湿的帐篷里，伤口隐隐作痛，身边战友低声咳嗽着。你递给他一口水袋，却看到她的额头上渗满细密的汗珠，脸色惨白如纸。兄弟，你没事吧？他摇摇头，勉强挤出一个虚弱的笑容，没事，睡一觉就好了。你安慰自己，或许只是一场风寒罢了。次日清晨，你被惊叫声惊醒。掀开帐篷，映入眼帘的是令人毛骨悚然的一幕。营帐外躺满了奄奄一息的士兵，个个面色青黑，口唇干裂，有人甚至瘫倒在地，挣扎着向前爬动，眼神里充满了绝望。军医惊恐的喊道，不好，是瘟疫。你的心猛然一沉，汗毛倒竖。将军急忙下令隔离病患，但帐篷早已塞满了呻吟的病人，军中恐慌迅速蔓延，没人知道下一个倒下的会不会就是自己。几日之内，军队士气瓦解，敌方的探子传来消息，宋军染棘，已无战力，敌军趁势攻来。你们这些幸存者仓促应战，但手中的刀剑却仿佛重于千金。你看着一个个面容憔悴的战友倒在自己身边，敌人的刀还未靠近，他们便已因疾病虚脱而倒下。城破那日，你被敌人俘虏，眼睁睁看着自己驻守多年的城池被付之一炬。被俘的路上，你听敌兵闲聊，多亏了这一场瘟疫，否则城池哪能这么轻松的攻破，你心中一阵苦涩。押解途中，你与其他战俘被关进一处偏僻村落等待处理。夜晚守卫，昏昏欲睡，你趁机挣脱绳索逃出，却发现逃亡之路更加艰难，一路上尽是荒村野尸，家家闭户并漂遍野。你踩着尸骸踉跄前行，所到之处如同人间地狱。你明白，瘟疫比战争更无情，它不分敌我，只留下一片焦土和尸骨。几经挣扎，你终于逃回故乡，却发现村庄早已空无一人，唯有乌鸦的哀鸣在回响。你失魂落魄的走进家门，地上躺着父母冰冷僵硬的尸体，桌上还有未曾吃完的晚饭。你跪倒在地无声的痛哭。就在此时，你感到身体传来一阵剧痛，低头一看，手臂上赫然出现了与战友一样的黑斑，你颤抖着手摸向额头，已示滚烫如炭火。此刻，你才惊恐的意识到，自己也早已成为瘟疫的牺牲品，只是一直苦苦挣扎，不愿面对。耳边依稀响起昔日战友的叹息，原来我们才是这场战争真正的失败者。临死之际，你终于明白，战争胜负的背后，瘟疫才是真正的主宰。

**输出要求**：只输出口播字幕文案，不要输出其他任何额外内容，不输出分段说明

主题：{{theme}}""",
            
            'en': """Please create a historical short video script based on the provided [THEME], following this structure:

1. **Suspenseful Opening**: Start with "[Dynasty/Setting] + Counter-intuitive question/claim" to grab audience attention (e.g., "Was being an ancient [profession] really better than being [comparison object]?").
2. **Identity Immersion**: Use second person "you" to describe the protagonist's identity, historical background, and life-threatening crisis (include specific position/situation/enemies), no transition words like "imagine", dive straight into the theme.
3. **Escalating Conflict**:
   - First layer: External pressure (enemy siege, superior oppression, natural disasters)
   - Second layer: Internal collapse (subordinate betrayal, resource shortage, disease spread)
   - Third layer: Moral dilemma (loyalty vs justice, massacre decision, political alignment)
4. **Solution Details**: Protagonist takes 3 progressive actions:
   - Intimidation tactics (public execution/evidence burning)
   - Psychological warfare (divide and conquer/anonymous letters)
   - Ultimate trump card (hidden documents/leveraging power)
5. **Thematic Conclusion**: Through protagonist's ending (pyrrhic victory/heroic failure) deliver a powerful message revealing historical truths (power essence/war reality/human nature).

**Requirements**:
- Each section no more than 3 sentences, use short phrases for tension
- Include at least 2 historical professional terms
- Use sensory descriptions at key turning points (smell/touch/visual impact)
- End with "At this moment you finally understand..." format
- Generate approximately 1000 words of narration script
- Mix long and short sentences, split long sentences with commas, each phrase under 19 characters

**Reference Examples**:
Example 1 - Roman Centurion:
Was being a Roman centurion in Gaul really more dangerous than facing gladiators in the arena? You are Marcus Aurelius Maximus, a seasoned centurion commanding the Third Cohort at the edge of the known world. The Germanic tribes are massing beyond the Rhine, their war drums echoing through the mist-shrouded forests. Your own men whisper of defeat, supplies run low, and winter approaches with merciless cold. The smell of fear mingles with woodsmoke in your camp. You stand before your wavering soldiers, voice cutting through their doubt like a blade through silk. "Romans do not yield to barbarians who paint their faces and howl at the moon." Your words ignite something primal in their hearts. Three days later, the attack comes at dawn. Arrows darken the sky like a swarm of locusts, shields splinter under the impact of Germanic axes. You feel warm blood on your face, but it's not your own. In that moment of chaos, you make three crucial decisions. First, you order the release of captured Germanic children - not from mercy, but to sow confusion in enemy ranks. Second, you spread rumors through a captured spy that Roman reinforcements are approaching from the south. Third, you reveal your secret weapon: Greek fire, smuggled from Constantinople months ago. The forest erupts in flames that seem to come from Hades itself. Germanic warriors flee in terror, believing they face the wrath of the gods. Your victory is complete, but pyrrhic - half your men lie dead or dying. Standing among the smoldering ruins, you finally understand the true cost of empire. At this moment you finally understand that glory is just another word for organized slaughter.

Example 2 - Medieval Knight:
Did medieval knights truly live by honor, or was it all just glorified thuggery? You are Sir William de Montfort, sworn sword to King Edward, riding through the plague-ravaged countryside of France. The Black Death has turned once-prosperous villages into charnel houses, and your mission grows more perilous with each passing league. Your destrier snorts nervously, sensing the corruption in the air that reeks of rotting flesh and burned timber. French peasants scatter at your approach, mistaking you for another reaver in steel. But worse enemies await - rival knights who have abandoned chivalry for banditry, preying on the weak and defenseless. At Château Noir, you discover the truth. Your own lord has been secretly selling grain to the enemy while English farmers starve. The revelation hits like a mace to the skull, shattering everything you believed about duty and honor. Now you face an impossible choice: obey your vows or follow your conscience. That night, you take decisive action. You forge documents implicating the traitorous lord in correspondence with French spies. You arrange for "bandits" to intercept his next grain shipment. Finally, you challenge him to single combat, knowing his guilt will make him hesitant and vulnerable. Your blade finds its mark between the plates of his armor, and he falls with a gurgling scream. As life fades from his eyes, you realize you've become everything you once despised. At this moment you finally understand that honor is a luxury only the living can afford.

Example 3 - Viking Warrior:
Were Viking raiders really just bloodthirsty savages, or was there method to their madness? You are Bjorn Ironside, son of Ragnar, leading your longship crew across the whale-road toward the rich monasteries of Northumbria. Salt spray stings your face as you grip the dragon-headed prow, but a darker storm brews among your own warriors. Half your crew questions your leadership, whispering that you're too young, too reckless. The stench of fear-sweat mingles with tar and seawater in the cramped ship's hold. When you beach your vessel on Saxon shores, treachery strikes like lightning. Your own blood-brother Ulf attempts to drive a seax between your shoulder blades, seeking to claim leadership for himself. But you've been expecting this betrayal - the signs were there in the way men's eyes avoided yours around the fire. Your response is swift and brutal. You grab Ulf's wrist, twist until bone snaps, and drive your knee into his ribs with crushing force. As he writhes in agony, you address the crew with iron in your voice: "Any who question Bjorn Ironside can test their courage against my axe." The taste of copper fills your mouth from his split lip, but your authority is restored. The monastery raid that follows is a masterpiece of calculated violence. You spare the scribes who can write ransom demands, burn only the buildings that hold no treasure, and ensure every Saxon survivor spreads word of your "mercy." This isn't mindless savagery - it's psychological warfare designed to make future conquests easier. Standing amid the smoking ruins, counting your plunder, you reflect on the price of leadership among wolves. At this moment you finally understand that true power comes not from the sharpest blade, but from knowing exactly when to sheathe it.

**Output Requirements**: Only output the narration script, no additional content or section labels

Theme: {{theme}}""",
            
            'es': """Por favor, crea un guión de video histórico corto basado en el [TEMA] proporcionado, siguiendo esta estructura:

1. **Apertura Suspensiva**: Comienza con "[Dinastía/Escenario] + pregunta/afirmación contraintuitiva" para captar la atención de la audiencia (ej: "¿Ser un [profesión] antiguo era realmente mejor que ser [objeto de comparación]?").
2. **Inmersión de Identidad**: Usa segunda persona "tú" para describir la identidad del protagonista, antecedentes históricos y crisis mortal (incluye posición/situación/enemigos específicos), sin palabras de transición como "imagina", sumérgete directamente en el tema.
3. **Conflicto Escalante**:
   - Primera capa: Presión externa (asedio enemigo, opresión superior, desastres naturales)
   - Segunda capa: Colapso interno (traición subordinada, escasez de recursos, propagación de enfermedades)
   - Tercera capa: Dilema moral (lealtad vs justicia, decisión de masacre, alineación política)
4. **Detalles de Solución**: El protagonista toma 3 acciones progresivas:
   - Tácticas de intimidación (ejecución pública/quema de evidencia)
   - Guerra psicológica (dividir y conquistar/cartas anónimas)
   - Carta de triunfo definitiva (documentos ocultos/aprovechar el poder)
5. **Conclusión Temática**: A través del final del protagonista (victoria pírrica/fracaso heroico) entregar un mensaje poderoso revelando verdades históricas (esencia del poder/realidad de la guerra/naturaleza humana).

**Requisitos**:
- Cada sección no más de 3 oraciones, usar frases cortas para tensión
- Incluir al menos 2 términos profesionales históricos
- Usar descripciones sensoriales en puntos de inflexión clave (olfato/tacto/impacto visual)
- Terminar con formato "En este momento finalmente entiendes..."
- Generar aproximadamente 1000 palabras de guión narrativo
- Mezclar oraciones largas y cortas, dividir oraciones largas con comas, cada frase bajo 19 caracteres

**Requisitos de Salida**: Solo salida del guión narrativo, sin contenido adicional o etiquetas de sección

Tema: {{theme}}"""
        }
    
    async def generate_script_async(self, request: ScriptGenerationRequest) -> GeneratedScript:
        """
        异步生成文案
        
        Args:
            request: 文案生成请求
        
        Returns:
            GeneratedScript: 生成的文案
        """
        start_time = time.time()
        
        try:
            # 缓存已禁用 - 每次都生成新内容
            
            # 验证请求
            if request.language not in self.supported_languages:
                raise ValueError(f"Unsupported language: {request.language}")
            
            if request.language not in self.prompt_templates:
                raise ValueError(f"No prompt template for language: {request.language}")
            
            # 构建提示词
            prompt_template = self.prompt_templates[request.language]
            prompt = prompt_template.replace('{{theme}}', request.theme)
            
            # 调用LLM API
            self.logger.info(f"Generating script: {request.language}/{request.theme[:20]}...")
            
            response = await self._call_llm_api(prompt)
            
            if not response:
                raise ValueError("Empty response from LLM")
            
            # 解析响应
            title, content = self._parse_response(response, request.language)
            
            # 创建结果对象
            result = GeneratedScript(
                title=title,
                content=content,
                language=request.language,
                theme=request.theme,
                word_count=len(content),
                generation_time=time.time() - start_time,
                model_used=self.llm_config.name
            )
            
            # 缓存结果
            cache_data = {
                'title': result.title,
                'content': result.content,
                'language': result.language,
                'theme': result.theme,
                'word_count': result.word_count,
                'model_used': result.model_used
            }
            
            # 缓存已禁用
            
            # 记录日志
            logger = self.config.get_logger('story_generator')
            logger.info(f"Content generation - Type: script_generation, Language: {request.language}, "
                       f"Input: {len(request.theme)} chars, Output: {len(content)} chars, "
                       f"Time: {result.generation_time:.2f}s")
            
            self.logger.info(f"Generated script successfully: {result.word_count} chars in {result.generation_time:.2f}s")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Script generation failed: {e}")
            
            # 记录错误日志
            logger = self.config.get_logger('story_generator')
            logger.error(f"Content generation failed - Type: script_generation, Language: {request.language}, "
                        f"Input: {len(request.theme)} chars, Time: {processing_time:.2f}s")
            
            raise
    
    async def _call_llm_api(self, prompt: str) -> str:
        """
        使用fallback机制调用LLM API
        
        Args:
            prompt: 提示词
        
        Returns:
            str: LLM响应
        """
        try:
            content = await self.llm_manager.call_llm_with_fallback(
                prompt=prompt,
                task_type='script_generation',
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens
            )
            
            if not content:
                raise ValueError("Empty response from all LLM providers")
            
            return content.strip()
            
        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            raise
    
    def _parse_response(self, response: str, language: str) -> Tuple[str, str]:
        """
        解析LLM响应，提取标题和内容
        
        Args:
            response: LLM响应
            language: 语言代码
        
        Returns:
            Tuple[str, str]: 标题和内容
        """
        lines = response.strip().split('\n')
        
        title = ""
        content_lines = []
        
        # 尝试识别标题
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # 检查是否为标题格式
            if (line.startswith('#') or 
                line.startswith('标题:') or 
                line.startswith('Title:') or 
                line.startswith('Título:')):
                title = line.lstrip('#').lstrip('标题:').lstrip('Title:').lstrip('Título:').strip()
                content_lines = lines[i+1:]
                break
            else:
                # 如果第一行看起来像标题（短且独立）
                if i == 0 and len(line) < 50 and '。' not in line and '.' not in line:
                    title = line
                    content_lines = lines[i+1:]
                    break
        
        # 如果没有识别到标题，使用第一行
        if not title and lines:
            title = lines[0][:30] + "..." if len(lines[0]) > 30 else lines[0]
            content_lines = lines
        
        # 处理内容
        content = '\n'.join(content_lines).strip()
        
        # 清理内容
        content = self._clean_content(content)
        
        return title, content
    
    def _clean_content(self, content: str) -> str:
        """清理生成的内容，移除结构标识词"""
        # 移除多余的空行
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # 结构标识词列表（需要过滤的词语）
        structure_keywords = [
            '悬念开场', '身份代入', '冲突升级', '破局细节', '主题收尾',
            '开场', '结尾', '总结', '段落', '第一部分', '第二部分',
            '**', '###', '##', '#', '创作要求', '写作技巧', '内容要求'
        ]
        
        # 移除可能的标记或格式符号
        cleaned_lines = []
        for line in lines:
            # 跳过纯标记行
            if line.startswith('---') or line.startswith('===') or line.startswith('**'):
                continue
            
            # 检查是否包含结构标识词
            contains_structure_keyword = any(keyword in line for keyword in structure_keywords)
            if contains_structure_keyword:
                self.logger.warning(f"Filtered out structure keyword in line: {line[:30]}...")
                continue
            
            # 清理行首的标记
            line = line.lstrip('- ').lstrip('* ').lstrip('> ').lstrip('1234567890. ')
            if line and len(line) > 3:  # 过滤过短的行
                cleaned_lines.append(line)
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # 最后检查：如果内容过短或仍包含结构标识，返回警告
        if len(cleaned_content) < 100:
            self.logger.warning("Generated content too short after cleaning, may need regeneration")
        
        return cleaned_content
    
    def generate_script_sync(self, request: ScriptGenerationRequest) -> GeneratedScript:
        """
        同步生成文案（对异步方法的包装）
        
        Args:
            request: 文案生成请求
        
        Returns:
            GeneratedScript: 生成的文案
        """
        return asyncio.run(self.generate_script_async(request))
    
    async def batch_generate_scripts(self, requests: List[ScriptGenerationRequest], 
                                   max_concurrent: int = 3) -> List[GeneratedScript]:
        """
        批量生成文案
        
        Args:
            requests: 文案生成请求列表
            max_concurrent: 最大并发数
        
        Returns:
            List[GeneratedScript]: 生成的文案列表
        """
        self.logger.info(f"Starting batch script generation: {len(requests)} requests")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(request: ScriptGenerationRequest) -> GeneratedScript:
            async with semaphore:
                return await self.generate_script_async(request)
        
        # 执行并发生成
        tasks = [generate_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果和异常
        successful_results = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Batch generation failed for request {i}: {result}")
                failed_count += 1
            else:
                successful_results.append(result)
        
        self.logger.info(f"Batch generation completed: {len(successful_results)} successful, {failed_count} failed")
        
        return successful_results
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """获取生成统计信息"""
        
        return {
            'supported_languages': self.supported_languages,
            'model_config': {
                'name': self.llm_config.name,
                'temperature': self.llm_config.temperature,
                'max_tokens': self.llm_config.max_tokens
            }
        }
    
    def save_script(self, script: GeneratedScript, output_dir: Optional[str] = None) -> str:
        """
        保存生成的文案到文件
        
        Args:
            script: 生成的文案
            output_dir: 输出目录（可选）
        
        Returns:
            str: 保存的文件路径
        """
        if not output_dir:
            filename = self.file_manager.generate_filename(
                content=script.content,
                prefix=f"script_{script.language}",
                extension="txt"
            )
            filepath = self.file_manager.get_output_path('scripts', filename)
        else:
            filepath = Path(output_dir) / f"script_{script.language}_{int(time.time())}.txt"
        
        # 准备保存内容
        content_to_save = f"""标题: {script.title}
语言: {script.language}  
主题: {script.theme}
字数: {script.word_count}
模型: {script.model_used}
生成时间: {script.generation_time:.2f}秒
生成于: {time.strftime('%Y-%m-%d %H:%M:%S')}

--- 文案内容 ---

{script.content}
"""
        
        success = self.file_manager.save_text(content_to_save, filepath)
        
        if success:
            self.logger.info(f"Saved script to: {filepath}")
            return str(filepath)
        else:
            raise Exception(f"Failed to save script to: {filepath}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ScriptGenerator(model={self.llm_config.name}, languages={self.supported_languages})"