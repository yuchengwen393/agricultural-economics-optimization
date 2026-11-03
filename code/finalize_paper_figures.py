"""用途：记录标准论文图的人工视觉验收，并保存最终文件索引。
生成逻辑：仅在主代理逐页查看当前PDF渲染后以--confirm-reviewed显式确认；
复核源文件SHA256、图数与渲染对应关系，不修改求解数据或图的像素。
"""
from pathlib import Path
import argparse
import hashlib
import json
import pandas as pd
from PIL import Image, PngImagePlugin


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-reviewed', action='store_true')
    args = parser.parse_args()
    if not args.confirm_reviewed:
        parser.error('须先逐图检查当前预览和最终PDF全部页面，再显式确认。')
    root = Path('D:/Desktop/code/08_标准论文图')
    qa_dir = root / '核对与预览'
    qa_path = qa_dir / '绘图验收.json'
    audit = json.loads(qa_path.read_text(encoding='utf-8'))
    source = pd.read_csv(root / '绘图数据来源与校验和.csv')
    for row in source.itertuples():
        assert sha(Path(row.path)) == row.sha256, f'来源发生变化：{row.path}'
    figures = pd.read_csv(root / '图表清单与生成逻辑.csv')
    assert len(figures) == 10 and int(figures.panels.sum()) == 37
    renders = sorted(qa_dir.glob('PDF_render-*.png'))
    assert len(renders) == 10 and audit['passed']
    pdf_sha = sha(root / '论文图集_标准版.pdf')
    for n, path in enumerate(renders, 1):
        assert path.name == f'PDF_render-{n:02d}.png'
        with Image.open(path) as im:
            im.load()
            info = PngImagePlugin.PngInfo()
            info.add_text('Description', f'用途：最终PDF第{n}页视觉验收预览，非投稿原图。生成逻辑：Poppler以120dpi渲染论文图集_标准版.pdf；源PDF SHA256={pdf_sha}。')
            im.save(path, pnginfo=info, dpi=(120, 120))
    audit['visual_qa'] = '主代理已逐图检查同源预览及当前最终PDF全部10页；已修正分类刻度省略和电池图图例遮挡，未发现缺字、裁切或影响判读的重叠。此为人工版式验收，不认证现场可执行性。'
    audit['visual_qa_evidence'] = {
        'pdf_sha256': pdf_sha,
        'render_dpi': 120,
        'render_pages': [p.name for p in renders],
        'render_sha256': {p.name: sha(p) for p in renders},
        'figure_count': 10,
        'panel_count_excluding_colorbar': 37,
        'source_files_rechecked': len(source),
        'reviewed_category_counts': {'county': 20, 'years': 11, 'teams': 5, 'OWN1_batteries': 3},
    }
    qa_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    report = f'''# 标准论文图严格核对报告

用途：说明本次标准绘图的数值、来源、字体与版式验收结论。生成逻辑：绘图脚本独立核算并保存检查事件，主代理逐页审阅最终PDF后由finalize_paper_figures.py锁定验收证据。

## 数值与来源

- 绘图阶段{audit['checks_count']}项检查全部通过，详细记录见核对与预览/绘图核对明细.csv。
- {len(source)}个绘图来源在绘图前后及最终交付时SHA256一致；原始数据、求解结果与05_论文图表旧图保留。
- 主方案及时面积、总面积、支出及最差组率独立重算。任务表重复记录的整包费用只按5个班组计一次，未逐任务重复计费。
- 61个天气日期及100组扰动按相同样本配对；均值、CVaR90与兑现率按未舍入数据核算，图内仅显示舍入标签。
- 资源图采用最终增强路线池；限时结果与不可行状态明确区分，缺解不补零。成本误差线为求解上下界，不是置信区间。
- ALNS使用实际三次轨迹及其中一条实际最佳方案；不同运行指标不拼接为虚构方案。真实子实例计算时间不包含完整列池生成。
- 天气箱线图和县域最小—最大范围不是置信区间，未添加未经计算的显著性标记。

## 字体与版式

- 共10张复合图、37个统计/布局子面板，色条不计子面板。
- 10图全部文字对象加粗。英文/数字Arial Bold，中文Microsoft YaHei Bold；最终PDF嵌入字体：{', '.join(audit['pdf_fonts'])}。
- PNG全部具有600dpi元数据；SVG采用字形路径以避免跨电脑缺字，图形可编辑；PDF空间栅格背景保持栅格，文字与线路为矢量。
- 白底、可区分配色与线型；主轴框1.25pt、辅助框0.6pt、曲线1.65pt、网格0.4pt。分类标签逐项显示，电池图图例置于绘图区外。
- 主代理已查看同源预览并检查当前最终PDF全部10页，未发现缺字、裁切或影响判读的重叠。PDF当前SHA256：`{pdf_sha}`。
- 多面板宽图应按建议宽度或横向排版，不建议强行缩为窄单栏。投稿应使用PNG_600dpi、SVG_矢量或PDF，核对与预览仅用于审阅。

## 解释边界

服务网格不是确权地块或真实订单，空间连线不是导航；历史气象代理与跨产品一致性不等于现场安全认证或站点真值精度。最近优先不满足最差组服务下限，鲁棒样本中100%兑现不等于普遍保证。DP排序与原方案转场时间的补水口径不同，不能直接声称净节时；条件风险代理改善不能转换成农户净收入。这些边界同时写入图内说明及图注与数据口径.md。
'''
    (root / '绘图数据严格核对报告.md').write_text(report, encoding='utf-8')
    records = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.name == '标准文件清单.csv':
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith('PNG_600dpi/'):
            purpose, logic = '论文插图高分辨率原图', '核对后Matplotlib导出600dpi PNG，内含用途元数据'
        elif rel.startswith('SVG_矢量/'):
            purpose, logic = '论文插图可编辑矢量版', '同源Matplotlib导出，字体字形路径化'
        elif rel.startswith('绘图数据/'):
            purpose, logic = '精确绘图数据与透明聚合', '逐文件purpose/generation_logic列说明来源与计算'
        elif rel.startswith('核对与预览/'):
            purpose, logic = '数值验收或视觉核对证据', '检查事件、同源预览或最终PDF渲染；不是投稿原图'
        else:
            purpose, logic = '标准论文图交付入口、图注或索引', '由最终图表与核对记录生成，正文说明用途及逻辑'
        records.append({'path': rel, 'bytes': p.stat().st_size, 'sha256': sha(p), 'purpose': purpose, 'generation_logic': logic})
    pd.DataFrame(records).to_csv(root / '标准文件清单.csv', index=False, encoding='utf-8-sig')
    print(f'Visual QA finalized: {len(figures)} figures, 37 panels, {len(source)} unchanged sources, {len(records)} indexed files.')


if __name__ == '__main__':
    main()
