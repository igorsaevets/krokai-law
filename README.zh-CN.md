# KrokAI Law — AI 法律文书引用核查工具：逐字核对每一处引文

[![selftest](https://github.com/igorsaevets/krokai-law/actions/workflows/selftest.yml/badge.svg)](https://github.com/igorsaevets/krokai-law/actions/workflows/selftest.yml)

**提交之前，把法律文书里的每一处引文都和真正的原文逐字核对一遍。**

<div itemscope itemtype="https://schema.org/SoftwareApplication">

AI 助手——ChatGPT、Claude、Gemini、DeepSeek——几分钟就能写出一份 USCIS 移民申请（petition）、一份 RFE 补件回复或一份法律文书（brief）。但它放进引号里的内容，有一部分在原文里根本不存在（也就是所谓的 AI“幻觉”）：法院从没写过的句子，被悄悄删掉了限制条件的法规，挂在错误出处下的正确文字。<span itemprop="description"><strong itemprop="name">KrokAI Law</strong> 是一款免费、开源的命令行工具：它把你文书中的每一处引文与你下载到本地的法律原文逐字比对，告诉你哪些引文对不上、差在哪里。它在你自己的电脑上运行：草稿不会上传到任何地方，判定结果也不由任何 AI 模型给出。</span>

*English: [README.md](README.md) · Русский: [README.ru.md](README.ru.md)*

| | |
|---|---|
| **痛点** | 编造或被篡改的引文看起来和真的一模一样，而签字的人要为它负责 |
| **办法** | 每一处引文都与你硬盘上的成文法、法规、政策手册（Policy Manual）章节或判例逐字比对 |
| **结果** | 一份需要修改的清单，并标出每个字所在的页码——在任何文件提交之前 |
| **价格** | 免费，<a itemprop="license" href="https://github.com/igorsaevets/krokai-law/blob/main/LICENSE">MIT 许可证</a>，无需账号，无需 API key |

</div>

---

## 问题：法律文书中的 AI 幻觉引文

**编造的引文看起来和真的一模一样。** 有人让一个模型打开一条联邦法规并引用它。模型打开了正确的页面，附上了正确、可以打开的链接——然后逐字编造了法规条文，放在引号里。所有“AI 有没有核查来源？”的审计都判定这个回答没有问题，因为这些审计检查的是页面有没有被*抓取*，而不是那些*文字*在不在页面里。

> **带有可用链接的引用，并不能证明引文是真的。**
> 只有把文字和文件本身对照，才能证明。

**法院现在每周都在处理这种事。** 一个专门收录 AI 幻觉文书相关裁决的公开数据库，在 2026 年 11 月 28 日共收录 **2,387** 件：其中 1,586 件在美国，622 件涉及虚假引文，968 件是律师使用了 AI（[AI Hallucination Cases](https://www.damiencharlotin.com/hallucinations/)）。

**签字的人要承担后果——移民案件也不例外。** 2026 年 6 月，美国联邦第九巡回上诉法院在一宗移民上诉案中，对两名律师各罚款 2,500 美元，并暂停他们在该院执业六个月，原因是诉状中有 “multiple nonexistent cases, misattributed quotations, and gross misrepresentations of real cases”（大意：多个不存在的案例、张冠李戴的引文，以及对真实案例的严重歪曲）（[Lnu v. Blanche, No. 24-4790](https://cdn.ca9.uscourts.gov/datastore/opinions/2026/06/03/24-4790.pdf)）。2026 年 10 月，移民上诉委员会（BIA）暂停了其中一人在该委员会、各移民法院**以及国土安全部（DHS）**的执业资格，而 USCIS 正是 DHS 的下属机构（[Matter of Sethi, 30 I&N Dec. 112 (BIA 2026)](https://www.justice.gov/eoir/media/1463921/dl)）。

**只问“这个案子存不存在？”是不够的。** 同一份裁定写道，称职的律师 “must do more than prompt generative AI, check that the citations provided by the AI are real and the subject matter roughly on point, and call it a day.”（大意：不能只是让 AI 生成内容、确认它给的案例真实存在且主题大致相关，就算完事）。被处罚的引文中有一句其实是真实的句子——只不过出自另一个案子。付费检索工具也不能幸免：一项针对 LexisNexis 和 Thomson Reuters 的 AI 法律检索工具的研究发现，它们 “each hallucinate between 17% and 33% of the time”（大意：幻觉率各在 17% 到 33% 之间）（[Magesh et al.](https://arxiv.org/abs/2405.20362)，*Journal of Empirical Legal Studies*，2025）。

**而且出错的不只是机器。** 这个工具要抓的错误，大约一半最后证明是人犯的。在一次对已发表材料的审计中发现：一个裁决被挂在另一个裁决的脚注下引用；一句引文中间被删掉了一个分句；十处标着“已核实”的引文，恰好停在限制它们的那几个词前面一个逗号的位置（`..., but do not include instances where...`）。深夜十一点疲惫的人就会犯这种错，拼写检查和重读都发现不了。

## 解决办法：把每一处引文和原文核对

1. **把你依据的法律放在一个文件夹里。** 成文法、法规、政策手册章节、判例——`krokai fetch` 从发布方逐字节下载，服务器和文件之间没有任何 AI 模型。
2. **照常写作**——用 ChatGPT、Claude、Gemini、DeepSeek 或其他任何助手，或者亲手写。
3. **运行 `krokai check`。** 每份草稿里的每一处引文都会得到一个判定：`verified`（已核实）、`not found`（未找到）、`truncated condition`（文字完全一致，但原文后面紧跟着 `unless…` 之类的限制条件）、`operator`（原文是 `must`，你写成了 `may`）、`found elsewhere`（文字存在，但不在你引用的那条规定里）等等——并标出 PDF 页码和原文自己印的页码。要提交的文件和笔记、研究材料分开报告。

可选的钩子（hooks）会在你的助手每写下一处引文时自动运行检查，而不是等有人想起来才查。

## 示例：第九巡回法院处罚的那句引文

裁定引用了诉状归于 *Kamalthas v. INS*, 251 F.3d 1279, 1284 (9th Cir. 2001) 的一句话——"An adverse credibility determination is not necessarily a death knell to CAT protection."——并认定："This quotation does not appear in Kamalthas."（这句引文并不在 Kamalthas 案中。）当这份判决在原文文件夹里时（用 `krokai fetch-precedent` 下载），只需要一条命令（输出有删节）：

```text
$ krokai quote "An adverse credibility determination is not necessarily a death knell to CAT protection."
corpus: 2 files, 0.0 MB of text

NOT FOUND
  absent from the corpus, AND the cited source is one you have - so this is the shape a fabrication makes

🔴 NOT FOUND is not the same as INVENTED. Rule these out in order - only what
   survives all of them is a defect in the quotation:
     1. the source was never downloaded - ...
     ...
     6. the quotation was rewritten in OUR file - ...
```

判决中真实存在的一句话：

```text
$ krokai quote "the BIA has plainly overrelied on its prior adverse credibility finding against Kamalthas and failed to consider evidence of the relevant country conditions in the record"
corpus: 2 files, 0.0 MB of text

VERIFIED
  word for word in a file in your sources folder - which is not the same as 'in force today'
  found in: law\251.F3d.1279.99-71081.html
```

`krokai check` 会一次性对所有草稿中的所有引文做同样的检查，并写出 `REPORT.md`（要改什么、差在哪里）和 `READING-LIST.md`（每一处提交件中的引文与它的原文段落并排）。被处罚的那句话本身是真实的：*Shrestha v. Holder*（9th Cir. 2010）在谈到 Kamalthas 时写了这句话，而法院认定 "It makes no difference that the quotation does in fact appear in another case"（引文确实出现在另一个案子里，这一点无关紧要）。如果 *Shrestha* 也在你的文件夹里，`check` 会在那里找到这些文字，并在 `Found in:` 下写出那个文件；对于用当事人名称引用的法院判决，它目前还不会单独把这种情况标为出处错误——请看那一行。

## 适用人群

- **撰写 USCIS 移民申请的人**——EB-2 NIW、EB-1A、O-1、I-140、I-485 调整身份、RFE 回复——无论是自己 DIY 申请，还是在小型事务所里，配合 AI 助手写作。
- **签署助手所写文书的移民律师和律师助理。** 内置的引用格式包覆盖 INA、CFR、美国法典（U.S. Code）、联邦公报（Federal Register）、USCIS 政策、FAM 以及 BIA 先例。
- **任何提交带引文的法律文本的人**——也附带一个税法包；加入你自己的法律体系只需要一个 JSON 文件，不需要改代码。

## 它和普通引用检查工具有什么不同

大多数引用检查工具回答的是“这个案子存在吗？”。少数商业工具也会把文书中的引文与它们自己数据库里的被引案例对比（见[已有的工具](#已有的工具以及本工具的不同之处)）。KrokAI Law：

- **核对文字**，而不只是核对出处——还会检查紧跟在引文后面的内容（`but`、`unless`、`except`），因为提前一个分句结束的引文，表述的是另一条规则；
- **核对移民申请所依据的法律**——法规、政策手册、AAO 和 BIA 的裁决、FAM——用的就是你所依据的那份副本，并标出每个字所在的页码；
- **让客户的文本留在你的电脑上**：检查在本地运行，外发闸门会在任何内容发给外部 AI 之前拦下凭据和个人身份信息；
- **结果确定**：判定是文本比对，而不是模型的意见——同一份草稿永远得到同一个答案；
- **免费、开源**（MIT），无需账号，无需 API key。

## 一分钟上手

```bash
pip install "krokai[all]"     # PDF, DOCX and web fetch included
cd /path/to/your/matter
krokai init .
krokai check
```

或者把本仓库的链接发给你的 AI 助手，告诉它 *"install this for me, including the hooks"*（帮我安装，包括钩子）——[INSTALL-FOR-AI.md](INSTALL-FOR-AI.md) 就是写给助手看的。所有安装方式以及如何更新：[见下文](#安装大约一分钟)。

## 常见问题

### 怎么检查 ChatGPT、Claude 或 DeepSeek 写的法律文书里有没有编造的引文？

把草稿依据的原文放进一个文件夹——`krokai fetch` 和 `krokai fetch-precedent` 会从发布方下载它们——然后运行 `krokai check`。文字不在任何原文里的引文会得到 `not found`；被改动或被截短的引文会按发生了什么来命名（`operator`、`truncated condition` 以及上面提到的其他判定）。无论草稿是模型写的还是人写的，检查方式都一样。

### 有免费的法律引用核查工具吗？

就是这个：免费、开源（MIT），无需账号，无需 API key，在你自己的电脑上运行。它核对的是引文的文字与你保存的原文是否一致。一个案子是否存在、是否仍然有效，是引证工具（citator）的工作（Westlaw 的 KeyCite、Lexis 的 Shepard's）。

### 能查出 AI 虚构的判例吗？

部分可以。`krokai fetch-precedent` 只有在你指定的当事人、主题和法院都出现在下载的判决文本中时才会保留这份判决，所以一个不存在的案子无法被下载进你的原文文件夹，归于它的引文会得到 `not found`——除非这些文字是真实的、并且出自你手上的另一份判决（[上面的示例](#示例第九巡回法院处罚的那句引文)就是这种情况）。它不会去判例数据库里查询一个引用。

### 我自己用 ChatGPT 或 Claude 写 EB-2 NIW 或 EB-1A 申请信（DIY），它检查什么？

草稿里的每一处引文——USCIS 政策手册、8 C.F.R.、INA、AAO 和 BIA 的裁决——都会与你硬盘上那份原文的副本比对，并标出每个字所在的页码。它不评判申请本身的胜算，也不判断证据是否满足标准。

### 我的文书会离开我的电脑吗？

不会。检查在本地运行。只有可选的第二意见命令（`krokai review`、`krokai check --judge`）会把文本发出去，发给你选择的模型，而且外发闸门会先拦下凭据和个人身份信息。

### 它和 Westlaw Quick Check、BriefCatch RealityCheck 有什么区别？

两者都是付费服务，用它们自己的数据库检查文书：Westlaw 把案例引文和 Westlaw Edge 对比，BriefCatch 检查被引的案例和联邦成文法。KrokAI Law 免费，在你的电脑上运行，检查的是你保存的副本——除了法院判决，还包括政策手册、法规和行政机关的裁决。详见[已有的工具](#已有的工具以及本工具的不同之处)。

### 能检查中文法律文书或中国法律吗？

逐字比对本身不挑语言：在一个人工构造的中文测试样例上，`krokai quote` 对原文中的句子给出 `VERIFIED`，对被改动（“应当”改成“可以”）或编造的句子给出 `NOT FOUND`。但有三点限制，都是实测结果：对限制词（`but`、`unless`）和情态词（`may`、`must`）的专门检查只认英文，所以截在“但是……除外”之前的中文引文仍会得到 `VERIFIED`；`krokai check` 只从草稿中提取 45 个字符以上的引文，而中文引文往往更短——短的请用 `krokai quote` 单独核对；内置的引用格式包只覆盖美国法律，中国法律没有引用格式包。

---

## 它实际做什么

**1. 核对文字。** 你写的所有内容中的每一处引文，与你下载的每一份原文对照。不是“大致对不对”，而是这串文字在不在。

**2. 核对出处。** 在*某个地方*找到这些文字，不等于在*你说的地方*找到它们。如果你的文书引用的是一条规定，而这句话其实在另一条里，工具会告诉你。

**3. 核对接下来的内容。** 法律写作中代价最高的错误，是一句完全正确、却提前一个分句结束的引文。`krokai` 会读取原文中紧跟在引文后面的内容，当接下来的词是 `but`、`unless`、`except`、`provided that` 时给出提示。

**4. 保存原文——并下载原文。** 一个引文库（quote bank），收录你亲自打开并确认过的所有引文，以及一个你已下载法律的索引。因为“我没找到”只有在你知道自己有没有下载过的时候才有意义。

`krokai fetch <url>` 自己把文本下载下来，它强制执行的唯一一条规则，正是它存在的理由：**服务器和文件之间不经过任何语言模型。** 让助手“抓取这条法规”，它会调用某种网页工具，先把页面转换一遍，再用一个小而快的模型针对页面回答提示——于是落到你硬盘上的，是*关于*这个页面的生成文本。拿它来核对引文，报告会显示 `VERIFIED`，而比对的对象其实是一段转述。`krokai` 原样写下服务器发来的字节，之后用读取其他所有文件的同一套代码去读它。

下载的文件先进入一个不参与检索的收件箱（inbox）。冒用它无权使用的官方名称的主机会被直接拒绝；工具一无所知的主机会如实说明，并需要加一个参数才能继续，因为检测器保持沉默并不等于推荐。

**5. 法律变了，它会发现。** 再次下载同一条规定，如果字节不同，`krokai` 会保留两个版本，记录改了什么，并**用新文本重新核对引文库中的每一处引文**。在 8 CFR 245 的 2024 年版和 2026 年版之间实测：89% 未变，57 句消失——而且通篇把 *alien* 改成了 *noncitizen*。凡是从旧版本中摘取的该部分引文，都会开始显示“在你的原文中未找到”，而这恰恰是编造引文的样子。

**6. 询问其他模型，同时也不信任它们。** 一个模型可能自信、流畅地出错。`krokai review` 把同一个问题发给多个模型——用的是你已经付费的 AI 订阅，不需要 API key——然后把**它们的**引文送进与你自己的引文同一个检查器。最后这一步才是关键：审阅者的回答是输入，不是证据。

**7. 阻止客户数据外泄。** 在任何内容发往任何地方之前，外发闸门会扫描其中的凭据和个人身份信息，报告类型和行号，并且**从不打印具体值**。凭据没有放行选项。

闸门**拒绝发送，而不是悄悄改写你的文书。** 这个区别是有意的——悄悄吞掉一个词的替换，会损坏它本要保护的东西，还把损坏记成“正常运行”——这也意味着工具会告诉你要改什么，而不是在你背后替你改。

它查找的范围是有意不完整的：门牌号会被拿掉，街道和城市保留，因为一个不知道你的客户住在哪个城市的审阅者，只会回答一个比你问的更笼统的问题。**姓氏是唯一需要你自己配置的部分**，写在 `casefile.json` 的 `surnames` 里：没有任何规则能分辨姓氏和名字，靠猜的规则会在满是法官和机构名称的文书里删错词。留空的话，闸门会明确说出来——它不会对一项从未运行的检查报告 `clean`。

**8. 让检查自动发生。** 可选的钩子会在你的 AI 把引文写进文书时触发——而不是等你记起来去检查。这是最重要的部分，原因见下文。

**9. 用你已经做出的判断来检查论证。** 引文的文字可以是对的，出处可以是对的，草稿却仍然可能依据一条引文库标为*对我方不利*的规则——这是在姐妹项目中逐字测到的典型情况：8 CFR 214.2(f)(8)(i) 在引文库里是 §Π-13（对我方不利），而同一份提交文件却把它当作自己的正面依据。`krokai coverage <草稿文件>` 运行字符串比对做不到的四项检查：**地雷**（草稿引用了引文库标为对我方不利的规则）、**未使用**（引文库有对我方有利的条目，草稿从未使用）、**只有转述**（引用了出处，但没有引文库中的逐字引文——摘要不是引文，按精确页码去查的审理人员会发现文字与原文对不上），以及**缺件的条目**（没有适用边界的条目，会被引用得比它允许的更宽）。配套命令：`krokai library --bank` 交叉对照资料库和引文库——一边是下载了却从未分析的文件，另一边是原文缺失的引文库条目。

**10. 为每一份缺失的原文给出下载命令。** 指出一个 `NOT_FOUND` 只是答案的一半；另一半是*如何下载那份具体的原文*，而一个不得不四处找 URL 的助手，要么编一个，要么放弃。`krokai library --suggest-fetches` 为原文不在硬盘上的每一个引文库条目打印一条可以直接运行的 `krokai fetch <URL>`——针对发布方有稳定请求级 URL 的引用类型（U.S. Code、Federal Register、Public Law、eCFR API）。对于在反爬虫层后面的那些（USCIS 政策手册、政策备忘录），它打印只能用浏览器下载的备用办法，而不是编造一个 URL。当引文旁边的引用指向受支持的发布方时，`krokai quote` 会在 `NOT_FOUND` 的排查清单下打印同一条命令。案件文件夹根目录下的 `SITE-ACCESS.md` 记录当前环境能访问哪些发布方，在第一次下载失败时更新。

**11. 用引文库生成法律依据附录，并重新核验。** 附录是提交文件中列出论证所依据规则的那一部分。传统上它是手工汇编的——也就是说，是根据起草人*记得*的引文库汇编的，而不是根据资料库仍然能核验的引文库。`krokai appendix` 在生成时对每一个引文库条目重新运行 `check`，把核验通过的内容按 CFR / U.S. Code / INA / Public Law / Federal Register / Policy Manual 分组，并把所有未通过核验的内容列在醒目的 `EXCLUDED` 部分，写明新的判定。悄悄剔除，正是被删掉的但书（proviso）进入提交文件的方式——这一部分拒绝沉默。在 8 CFR 245 的两个版本之间实测：32 句消失；所有受影响的引文库引文都会得到 `NOT_FOUND`。昨天生成的附录不会发现这一点；这个会，因为它没有缓存。

**12. 证明你下载的判例就是你要的那一个。** 一个被要求保存 `Matter of Smith` 裁决的助手，保存了另一个 Smith、结论也不同——同一卷判例汇编，错误的文件。URL、链接文字和文件名看起来都没问题；只有读取提取出的文本才能发现。`krokai fetch-precedent <URL> --party X --subject Y --court Z` 下载裁决，**并且**要求当事人、主题和法院出现在提取文本的前 200 KB 中，才会保留这个文件。缺少任何一项，下载就会立即从收件箱中删除。没有 `--force`——下错文件这种失败，没有无害的形态。

---

## 为什么要第二意见，以及为什么它不是单独的下载

一个模型可以给出流畅、有出处、自信却错误的回答——而你从回答本身看不出来。多个模型出错的方式各不相同，所以它们之间的**分歧**才是信号。这就是要问不止一个模型的全部理由。

但询问多个模型只是一半。在这个工具的来源系统上实测：

- 一个渠道给出了一句引文、前后两句上下文，以及一个声称它打开过该页面的标记——三样全是编的；
- 两个渠道对**同一个**精确页码给出了两段**不同**的“逐字”文本。一个引的是该裁决本身；另一个引的是后来一个裁决对它的转述。挂在第一个精确页码下提交，就是把另一个权威的话放到了这个权威的地址下；
- 五个渠道彼此一致，而且每一个返回的都是提问者自己的错误，因为预期答案的一个片段就藏在问题里。

所以，审阅者的回答要和你自己的草稿一样，经过同一个检查器。**这是编排工具在结构上做不到的一步**——它有你的问题和它们的回答，却没有你的资料库。

如果你已经在用专门的多模型工具，`krokai` 会把同一份经过闸门的简报交给它，并审核它带回来的一切。如果没有，内置渠道会用你已有的订阅运行。无论哪种方式，命令都能用，因为一个需要再安装一个名字不同的程序才能用的功能，大多数人永远不会真正拥有。

---

## 塑造了整个设计的那个发现

一个指令文件用粗体写着：*每输入一处引文就核对一处。* 这条指令被认真执行——然后，在连续三次工作会话中，**检查器一次都没有运行**，而这些会话照样产出了新的引文。

规律可以解释这一点。只要任务本身就是核对，一切都正常。任务一旦变成策略，这一切就都沉默了。

> **规则按话题触发，而不是按规则触发。**

指令是和你眼前的工作争夺注意力的文本。当工作*就是*这条规则时，规则赢。当工作是别的事情时，规则输——而且没人注意到，因为一条没有触发的规则不会留下任何痕迹。

实测代价：**16 轮对话产出了法律引文，却一条都没有存入引文库。** 最糟的一轮产出了 65 处引文，一条都没存。后来核对这 108 处引文，发现其中 21 处在硬盘上的任何原文里都不存在。

钩子由运行环境执行，而不是由助手执行。话题影响不了它。这就是钩子存在的全部理由，也是为什么这是一个工具而不是一张检查清单。

同一次测量还有后半段：即使一处引文**被**存入了引文库，也得有人去抄它——而模型是在生成文本，不是在复制文本。在来源项目中，凭肉眼重新输入六处引文库引文，六个标记丢了两个。所以引文库由一个把关程序来写：`krokai bank add`：你给出开头的几个词和结尾的几个词，工具把两者之间的文字从原文文件中切出来——引文从不出现在参数里，所以也就没有可以打错的地方。切片在写入*之前*就会被核验（停在 `except as provided…` 之前一个分句的切片会被拒绝，并在屏幕上显示被丢掉的后续内容），出处会与文件对照，*这条引文不能证明什么*的边界是必填项，写入成功后会自动勾掉队列中对应的那一行。默认是试运行；加 `--apply` 才写入。

---

## 安装：大约一分钟

```bash
pip install krokai            # or: pip install "krokai[all]" for PDF + DOCX + web fetch
cd /path/to/your/matter
krokai init .
krokai check
```

**不需要编程，无需账号，无需 API key，没有任何东西离开你的电脑。** 五种安装方式，包括为受限的工作电脑准备的纯文件复制：[INSTALL.md](INSTALL.md)。

**或者交给你的 AI。** 把仓库链接发给它，告诉它 *"install this for me, including the hooks"*——[INSTALL-FOR-AI.md](INSTALL-FOR-AI.md) 是写给助手而不是写给你的，它在最后会自己验证安装结果。

### 更新已有的安装

一个子命令。在案件文件夹里，或者任何你的 `krokai` 命令能运行的地方：

```bash
python -m krokai upgrade         # or:  python /path/to/krokai-law/krokai upgrade
```

它会判断这份副本是在 `site-packages` 下（用 pip）、在 git 克隆里（用 git），还是在复制来的文件夹里（打印如何重新复制），运行对应的工具，刷新当前案件文件夹中的钩子，并打印改了什么。`--dry-run` 只报告检测到的布局和它将运行的确切命令，不做任何改动。

**或者交给你的 AI。** 把仓库链接发给它，告诉它 *"update this for me"*——同一个 [INSTALL-FOR-AI.md](INSTALL-FOR-AI.md#updating-an-existing-install) 文件里有一个写给助手的“Updating”部分。

---

## 你会得到什么

```
verdict                A filed B guides C research
truncated condition          2       0       0
operator                     1       0       1
found elsewhere              1       0       0
not found                    0       1       4
verified                    38      12      61
```

你自己写的内容按出错的代价分级：A 级是要提交的文件，B 级是指南，C 级是研究笔记。研究笔记里一处不严谨的引文，和一份要送出门的文件里的同样问题不是一回事，把它们混在一起，会从两个方向同时扭曲数字。

每一项发现都写明文件、引文、在哪份原文中找到，以及**具体差在哪里**——不是“存在不一致”，而是 `not`，或者 ``the source also has `*` ``，或者*原文接着写道："…, but do not include instances where…"*。

**页码，两种。** PDF 中的一处匹配会写明文件的页码和原文自己印的页码：`PDF page 4 of 12, printed page 299`——即页面上单独一行显示的那个数字，只有当文件中带编号的页面都符合同一个序列时才采用（不显示页码的页面，只在两个显示页码的页面之间才计入）。GPO 出版的 Federal Register 或 Statutes at Large 文本按它自己的页码标记分页（`printed pages 41300-41301`、`110 STAT. 3009-546`）。当原文什么都证明不了时——没有页码、两个序列、页面在编号范围之外——这一行会写 `printed page unknown` 并说明原因。这是文件自己印的页码：判例汇编的重印本印的是汇编的页码，裁判单行本（slip opinion）印的是它自己的页码，所以只有当文件就是汇编本身的印本时，才拿它来和精确页码（pincite）对比。

**裁决中的区域。** 在 I&N Dec. 裁决中，`quote` 和 `check` 还会写明文字所在的部分：`zone: the opinion`（正文意见）；`zone: the headnote only, not the opinion`（只在编者摘要里，不在正文意见里）——编者摘要是 EOIR 发布裁决时加在意见上方的摘要（它的政策手册第 III 部分第 1.4 章：«Headnotes are added»），所以精确页码应当依据意见本身的文字；或者 `zone: a separate opinion only - «DISSENTING OPINION: …»`（只在单独意见里，例如反对意见），这也会使该引文成为 `WRONG_SPEAKER`。这些部分是根据裁决在它们之间印出的行来识别的——标题下第一行律师、指控或合议庭信息，反对意见的标题——一份什么都没印的裁决就是 `zone unknown`，并说明原因。一个文件只根据它自己的开头被识别为裁决；法院判决不划分区域。

在 `REPORT.md` 旁边，每次 `check` 都会写出 `READING-LIST.md`：提交文件中的每一处引文，连同使用它的那句话和原文中它周围的段落，被标记的排在前面。一处逐字正确的引文是否真的*支持*它所在的那句话，是一个需要阅读的问题，所以干净的引文不带任何“通过”标签——只带那些让一处引文排得靠前的客观事实（文字旁边有限制词——在列表中只看列表的开头、被引的那一项以及最后一项之后的内容，从不看相邻的项——有省略的文字，旁边没有出处）。

**可选：让一个模型先读一遍（`check --judge <channel>`）。** 除非你在命令行中要求，否则不启用。使用 `channels.json` 中一个设好了 key 和 `model` 的 HTTP 渠道，`check` 会为每一处干净的提交件引文、在它出现的每个草稿位置发送一次请求——草稿中的那句话（当引文单独成句时再加上前一句）、引文、它旁边的出处，以及清单中显示的那段原文；不发送文件名，也不发送草稿的其他内容——并把模型存疑的引文（夸大、漏掉条件、有一个例外恰好覆盖该句自身的事实）排在 `READING-LIST.md` 第 2 部分的最前面。它改变的只有这个顺序：没有判定、没有 `REPORT.md` 中的行、不影响退出码，模型的标签或理由也从不写在引文旁边，因为写在一行旁边的标签就是人们会照做的建议。每一个请求都会先带着该案件的 `surnames` 经过 `gate`；被闸门拦下的请求不会发出。缺少 key、未设置模型或模型调用失败，清单都会保持原来的顺序。控制台会打印发出了什么、拦下了什么、花费和耗时。

### 判定结果，用大白话说

| | |
|---|---|
| **verified** | 这些文字原样出现在**你原文文件夹中的**某个文件里——请读表格下面的警告 |
| **truncated condition** | 🔴 完全一致——但原文接下来是限制它的那个分句 |
| **truncated opening** | 🔴 完全一致——但它前面有一个被你截掉的否定词 |
| **operator** | 🔴 像 *not*、*unless*、*only*、*may*、*shall* 这样的词不同 |
| **found elsewhere** | 🔴 这些文字存在，但不在你引用的那条规定里 |
| **spliced** | 🔴 你的省略号把两份文件拼成了一句话 |
| **ellipsis hides** | 片段都在；但 `…` 删掉的内容缩小了规则的范围 |
| **altered** | 开头在原文里，整体不在——后半部分被改了 |
| **partial** | 一半在——去读原文 |
| **not found** | 不存在：要么没下载，要么不是真的 |
| **wrong speaker** | 逐字一致——但原文是在引述一位*评论者*的话，而不是在陈述规则 |
| **punctuation** | 文字和顺序相同，标点有出入 |
| **typesetting** | 你的引文没问题；是硬盘上的副本损坏了 |
| **scattered** | 每一句都是真的；但它们在原文中并不相邻 |
| **assembled** | 带省略号的引文，所有片段都按顺序存在，没有隐藏任何实质内容 |

> 🔴 **`verified` 不代表什么。** 它的意思是这些文字出现在你放进原文文件夹的某个文件里。它不代表这条规则现行有效，不代表这个文件是最新版本，不代表下载完整，也不代表你下载的网站就是真正的那个网站。一条已废止的法规照样完美通过核验。去年的年度版本也一样，一个在下载途中丢掉了六个要点中两个的章节也一样。
>
> 这正是这个工具自己的头号缺陷对准了它自己，而且不是猜测：四位独立的外部审阅者被分别问到这个设计对自身看不到什么，四位都给出了同一个答案——资料库是一组来源只是被**声称、从未被证明**的下载文件。这里没有任何东西检查签名、发布日期或保管链。`krokai library` 告诉你你有什么、什么时候下载的。判断它是否仍是现行法律，是律师的工作，这个工具不做。

---

## 已有的工具，以及本工具的不同之处

其中大多数是由这个设计的外部审阅者而不是作者本人找到的，这是报告已有工作（prior art）的诚实方式；最后两个引文检查工具是 2026 年 11 月 28 日加入的。功能描述来自各项目自己的页面；这里没有测试过其中任何一个。

| | 它做什么 | 本工具的不同之处 |
|---|---|---|
| [eyecite](https://github.com/freelawproject/eyecite)（开源） | *"Find legal citations in any block of text"*（在任意文本中找出法律引用） | 提取，而不是核验。非常擅长这一步之前的那一步 |
| [citereview](https://github.com/kirinccchang/citereview)（开源） | 通过 CourtListener、Cornell LII、GovInfo 验证引用 | 检查引用是否**存在**；本工具检查**文字**是否与你硬盘上的副本一致 |
| Clearbrief、ProofBrief、briefcheckr（商业） | 在 Word 中做引用检查，依托商业数据库 | 集成在 Word 中、依托数据库；本工具是一个你自己掌控的本地资料库，离线运行，不按席位收费 |
| Tracelaw（商业） | 运行多个前沿模型并交叉验证结果 | 最接近第二意见那一半——但交叉验证是在模型之间进行，而不是对照你手上的原始文本 |
| [Westlaw Quick Check Quotation Analysis](https://legal.thomsonreuters.com/en/c/quick-check-quotation-analysis)（商业） | *"shows differences such as missing, added, or changed language between case quotes in your uploaded document, and the cited case language on Westlaw Edge"*（显示你上传的文件中的案例引文与 Westlaw Edge 上被引案例原文之间缺失、增加或改动的语言） | 针对厂商数据库中的判例法、针对上传的文件；本工具检查你自己硬盘上的成文法、法规、行政指引和裁决，不上传任何东西 |
| [BriefCatch RealityCheck](https://www.briefcatch.com/realitycheck)（商业） | *"verifies cited cases and federal statutes"*（核验被引的案例和联邦成文法），并标出 *"Quotations that do not match the source text"*（与原文不符的引文） | 一项对照厂商原文检查的付费服务；本工具在你自己的电脑上，与你持有的副本比对 |

没有发现其中任何一个做到这种组合：**在你自己硬盘上的资料库中逐字节核对，再加上多模型第二意见、并把它们的引文送进同一个检查器。** 三次独立检索都没有确认存在这样的工具。这只是关于三次检索的陈述，不能证明不存在——如果你知道有，请提一个 issue，因为用现成的工具比维护这个省事得多。

---

## 它不做什么，直说

- **它不知道一条规则是否仍然有效。** 它对照的是你硬盘上的副本。一条已废止的法规照样完美通过核验。
- **它发现不了：正确的文字挂在同一份文件错误页码的精确页码下。** 一份已发表的清单曾经引用了某个裁决的编者摘要，引用的却是正文意见的页码，而意见中那句话的写法差了一个关键的词。两句话都真实存在于这份 PDF 中。对此本工具会说 *verified*，而且永远会这么说。
- **它不是律师，不提供法律意见。** 它只回答一个问题：这些文字在不在那份文件里。
- **一个标记也可能意味着工具错了。** 你下载的原文副本本身可能不完整——实测：一个抓取下来的行政机关章节只有六个要点中的四个，于是一处对缺失文字的*正确*引文被标记了出来。在你因为一个标记去“修改”文书之前，先打开线上页面看看。排查的顺序会随每一次未命中一起打印出来。
- **它目前还不能可靠地把用当事人名称引用的法院判决对应到它的文件。** 一处存在于你硬盘上另一份判决中的引文会被判为找到，只有 `Found in:` 那一行会显示它是在哪份判决中找到的——就是上面示例中的 *Shrestha* 案。

---

## 箱子里还有

- **一道防止把客户数据发给 AI 的闸门。** 其中 10 种凭据检测器不允许绕过，12 种个人身份信息检测器可以显式放行。它报告类型和行号，**从不报告具体值**——为了证明检查有效而把匹配内容打印出来，会把它泄露到对话记录里，那是早一步犯同样的错误。
- **防止模型拒绝法律工作的提示语**——以及证明拒绝是因为措辞而不是因为话题的测量。同样六个问题，作为*策略*提问被拒绝，作为*原文核验*提问则得到完整回答。[FEATURES.md](FEATURES.md#prompts)
- **一行能测出效果、阻止编造引文的话：** *a fabricated quotation is worse than a refusal*（编造的引文比拒绝回答更糟）。加上这句话后，一个模型三次中有三次回答“我不记得确切的措辞”，并指出这句话就是原因。
- **PDF 文本副本（sidecar），** 因为你的搜索工具不读 PDF，而且从没告诉过你。在一个资料库里，这样的文件有 67 个——占 35%——对所有搜索都不可见，所以关于它们的每一次“我找过了，什么也没有”都是假阴性。
- **一套回归测试工具（regression harness）**，它对检查器已经放行的引文做变异——插入一个 `not`、在但书之前截断、把两份原文焊在一起——然后统计其中还有多少被判为干净。在测试中免费发现漏洞，而不是在提交的文件里。

---

## 参考

逐个功能的完整参考，附每个功能背后的事件：**[FEATURES.md](FEATURES.md)**（英文）

如果读者是你的 AI 助手，为它写的工作规范是 **[AGENTS.md](AGENTS.md)**——与 `krokai agents` 在任何安装方式（克隆或 pip）下打印的文本相同。

---

## 发现 bug？想要新功能？想合作？

| 什么事 | 去哪里 |
|---|---|
| 有东西坏了，或者某个判定是错的 | [提一个 issue](../../issues)——附上引文、原文、你得到的判定和你期望的判定 |
| 想法、问题、你希望有引用格式包的某个法律体系 | [discussions](../../discussions) |
| 安全问题 | [私密报告](../../security/advisories/new)——**不要**发公开 issue |
| 合作、咨询，或者只是聊聊 | [LinkedIn](https://www.linkedin.com/in/igorsaevets/) · [Facebook](https://facebook.com/igorsaevets) · [GitHub](https://github.com/igorsaevets) |

**这里有意不提供联系邮箱。** 本仓库提交记录上的地址是 GitHub 的 no-reply 中转地址：它能正确标注提交者，但**根本没有邮件交换服务器**，发到这个地址的邮件会被直接丢弃，不会退信。一个悄悄吞掉 bug 报告的渠道，比没有渠道更糟。请使用上面的链接。

维护者 **Igor Saevets**（[@igorsaevets](https://github.com/igorsaevets)），洛杉矶。

许可证：MIT。这里没有任何东西会联系厂商，也没有任何测试需要 key。
