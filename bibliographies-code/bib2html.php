<?php

# php bib2html.php [webis|theses|pan] <bib-file> [<bib-file> [...]]

$root = "https://webis.de";
$owner = "webis-de";
$repo = "downloads";
$branch = "master";
$resourcesBase = "publications";
$sortEntries = true;

switch ($argv[1]) {
    case "webis":
        break;
    case "theses":
        $root = "https://webis.de";
        $owner = "webis-de";
        $repo = "downloads";
        $resourcesBase = "theses";
        break;
    case "pan":
        $root = "https://pan.webis.de";
        $owner = "pan-webis-de";
        $repo = "downloads";
        $resourcesBase = "publications";
        break;
    case "touche":
        $root = "https://touche.webis.de";
        $owner = "touche-webis-de";
        $repo = "downloads";
        $branch = "main";
        $resourcesBase = "publications";
        break;
    case "wsdm-cup":
        $root = "https://pan.webis.de";
        $owner = "pan-webis-de";
        $repo = "downloads";
        $resourcesBase = "publications";
        $sortEntries = false;
        break;
    default:
        fprintf(STDERR, "Unknown target: '" . $argv[1] . "'. Known are: 'webis', 'theses', and 'pan'.\n");
        exit();
}


$downloadsHref = $root . "/" . $repo;

$bibentries = new Bibentries();

// read
foreach ($argv as $bib_file) {
    if (preg_match('/\.bib$/', $bib_file)) {
        $bibentries->addBib($bib_file);
    }
}
error_log("  by checking the papers, slides, etc. found at https://github.com/" . $owner . "/" . $repo . "/tree/" . $branch . "/" . $resourcesBase . ".");

// sort
if ($sortEntries) {
  uksort($bibentries->entries, 'compare_keys');
}
function compare_keys($key1, $key2)
{
    global $bibentries;
    $year1 = substr($key1, strpos($key1, ":") + 1, 4);
    $year2 = substr($key2, strpos($key2, ":") + 1, 4);

    if ($year1 != $year2) {
        return -strcmp($year1, $year2);
    } else {
        $entry2 = $bibentries->entries[$key2];
        if (!isset($entry2['month'])) {
            return 1;
        }
        $entry1 = $bibentries->entries[$key1];
        if (!isset($entry1['month'])) {
            return -1;
        }

        $month1 = array_search($entry1['month'], array_keys(Bibentries::$month_names));
        $month2 = array_search($entry2['month'], array_keys(Bibentries::$month_names));
        return $month2 - $month1;
    }
}

// get which resources exist in the repository
function get_existing_href()
{
    global $owner;
    global $repo;
    global $branch;
    global $resourcesBase;

    $context = stream_context_create(array("http" => [
        "header" => "Accept: application/vnd.github.v3+json\r\n" .
            "User-Agent: webis-de\r\n"
    ]));

    $trees = json_decode(file_get_contents("https://api.github.com/repos/" . $owner . "/" . $repo . "/git/trees/" . $branch, false, $context));
    $url = false;
    foreach ($trees->tree as $tree) {
        if ($tree->path === $resourcesBase) {
            $url = $tree->url;
            break;
        }
    }

    if ($url) {
        $data = json_decode(file_get_contents($url . "?recursive=1", false, $context));
        $hrefs = array();
        foreach ($data->tree as $entry) {
            $hrefs[$entry->path] = 1;
        }
        return $hrefs;
    } else {
        error_log("Did not find tree for " . $resourcesBase);
        exit(1);
    }
}

$existingHrefs = get_existing_href();

// print
echo '{% raw %}' . "\n";

$lastEntryYear = "";
foreach ($bibentries->entries as $key => $entry) {
    $colonPos = strpos($key, ":");
    if ($colonPos !== false) {
        $year = substr($key, $colonPos + 1, 4);
        if ($year != $lastEntryYear) {
            if ($lastEntryYear != "") {
                echo '</div>' . "\n";
            }
            echo '<div id="year-' . $year . '" class="year-entry">' . "\n";
            echo '  <h2 class="year">' . $year . '</h2>' . "\n";
        }
        $bibentries->printEntry($key);
        $lastEntryYear = $year;
    }
}
echo '</div>' . "\n" . '{% endraw %}'. "\n";

function trim_value(&$value)
{
    $value = trim($value);
}

class Bibentries
{
    public static $paperRequestSubject = "?subject=Request%20file%20of%20publication%20";

    public static $month_names = array(
        "jan" => "January",
        "feb" => "February",
        "mar" => "March",
        "apr" => "April",
        "may" => "May",
        "jun" => "June",
        "jul" => "July",
        "aug" => "August",
        "sep" => "September",
        "oct" => "October",
        "nov" => "November",
        "dec" => "December");

    public static $escapeseq = array(
        "``" => "\"",
        "''" => "\"",
        "\\ " => " ",
        "\\_" => "_",
        "\\-" => "",
        "\\@" => "@",
        "\\&" => "&amp;",
        "\\aa" => "&aring;",
        "\\'a" => "&aacute;",
        "\\'A" => "&Aacute;",
        "\\`a" => "&agrave;",
        "\\~a" => "&atilde;",
        "\\\"a" => "&auml;",
        "\\ka" => "&#261;",
        "\\\"A" => "&Auml;",
        "\\'c" => "&cacute;",
        "\\c c" => "&ccedil;",
        "\\cc" => "&ccedil;",
        "\\c C" => "&Ccedil;",
        "\\cC" => "&Ccedil;",
        "\\c s" => "&#351;",
        "\\c t" => "&#355;",
        "\\d S" => "&#7778;",
        "\\'e" => "&eacute;",
        "\\'E" => "&Eacute;",
        "\\`e" => "&egrave;",
        "\\`E" => "&Egrave;",
        "\\^E" => "&Ecirc;",
        "\\^e" => "&ecirc;",
        "\\H u" => "&#369;",
        "\\\"i" => "&#239;",
        "\\'i" => "&iacute;",
        "\\i" => "&#305;",
        "\\l" => "&#322;",
        "\\L" => "&#321;",
        "---" => "&mdash;",
        "~" => "&nbsp;",
        "--" => "&ndash;",
        "\\'n" => "&nacute;",
        "\\~n" => "&ntilde;",
        "\\Ho" => "&odblac;",
        "\\o" => "&oslash;",
        "\\O" => "&Oslash;",
        "\\'o" => "&oacute;",
        "\\'O" => "&Oacute;",
        "\\\"o" => "&ouml;",
        "\\\"O" => "&Ouml;",
        "\\sc" => "",
        "\\'s" => "&sacute;",
        "\\'S" => "&Sacute;",
        "\\ss " => "&szlig;",
        "\\ss" => "&szlig;",
        "\\textsc" => "",
        "\\u a" => "&#259;",
        "\\u g" => "&#287;",
        "\\'u" => "&uacute;",
        "\\`u" => "&ugrave;",
        "\\\"u" => "&uuml;",
        "\\\"U" => "&Uuml;",
        "\\vc" => "&Ccaron;",
        "\\vc" => "&ccaron;",
        "\\vr" => "&rcaron;",
        "\\vS" => "&Scaron;",
        "\\vs" => "&scaron;",
        "\\vZ" => "&Zcaron;",
        "\\vz" => "&zcaron;",
        "\\v C" => "&Ccaron;",
        "\\v c" => "&ccaron;",
        "\\v r" => "&rcaron;",
        "\\v S" => "&Scaron;",
        "\\v s" => "&scaron;",
        "\\v Z" => "&Zcaron;",
        "\\v z" => "&zcaron;",
        "\\'y" => "&yacute;"
    );

    function Bibtex()
    {
        $this->entries = array();
    }

    function addBib($file)
    {
        if (!is_file($file))
            die;
        $fid = fopen($file, 'r');
        $this->parse($fid);
        fclose($fid);
    }

    function cleanValue($value)
    {
        $value = ltrim($value);
        $value = rtrim($value, ',');

        $value = strtr($value, array('}' => '', '{' => ''));
        $value = strtr($value, self::$escapeseq);
        $value = rtrim($value, '.');

        return $value;
    }

    function parse($fid)
    {
        while ($line = fgets($fid)) {
            $plainline = $line;
            $line = trim($line);
            if (strpos($line, '@') === 0) {
                $n = sscanf($line, '@%[^{]{%[^,],', $class, $bibkey);
                $this->entries[$bibkey] = array("class" => strtolower($class));
                $this->entries[$bibkey]['plain'] = $plainline;
            } else if (strpos($line, '%') === 0) {
                // do nothing: it is a comment
            } else if (($pos = strpos($line, '=')) !== false) {
                if (!isset($bibkey)) {
                    error_log("Undefined bibkey at line: " . $line);
                }
                $key = strtolower(trim(substr($line, 0, $pos)));
                $value = trim(substr($line, $pos + 1));
                $value = $this->cleanValue($value);
                $this->entries[$bibkey][$key] = $value;
                // annotations, links, and labels not shown in bibtex
                if (!in_array($key, array('annote', 'request', 'keywords', 'mentor', 'arxivpassword', 'options')) && ($key === 'url' || substr($key, -3) !== 'url')) {
                    $this->entries[$bibkey]['plain'] .= $plainline;
                }
            } else if (isset($bibkey)) {
                $this->entries[$bibkey]['plain'] .= trim($plainline);
                if (strpos($line, '}') === 0) {
                    unset($bibkey);
                }
            }
        }
    }

    function wrap($tag, $attributes, $content)
    {
        $attrstr = '';
        ksort($attributes);
        foreach ($attributes as $key => $value) {
            $attrstr = $attrstr . sprintf(' %s="%s"', $key, $value);
        }
        return sprintf('<%s%s>%s</%s>', $tag, $attrstr, $content, $tag);
    }

    function printPlainEntry($bibkey)
    {
        if (!isset($this->entries[$bibkey])) {
            echo('Bibentry not yet available.');
        } else {
            echo($this->entries[$bibkey]['plain']);
        }
    }

    function buildBibKeyByFilename($filename)
    {
        // extract bibkey based on filename
        $info = pathinfo($filename);
        $bibkey = basename($filename, '.' . $info['extension']);
        $bibkey = str_replace('_', ':', $bibkey);
        return $bibkey;
    }

    /**
     *   \brief test if bibkey is aviable
     **/
    function hasBibEntry($bibkey)
    {
        return isset($this->entries[$bibkey]);
    }

    function hasBibEntryByFilename($filename)
    {
        $bibkey = $this->buildBibKeyByFilename($filename);
        return $this->hasBibEntry($bibkey);
    }

    function getHrefIfExists($path, $bibid)
    {
        global $existingHrefs, $resourcesBase, $downloadsHref;
        $filename = $path . "/" . $bibid . ".pdf";
        if (isset($existingHrefs[$filename])) {
            return $downloadsHref . "/" . $resourcesBase . "/" . $filename;
        } else {
            return false;
        }
    }

    function printEntry($bibkey)
    {
        if (!isset($this->entries[$bibkey])) {
            echo "Missing bibkey: " . $bibkey;
            return;
        }

        $bibkeyclean = str_replace(":", "_", $bibkey);
        $bibid = str_replace(':', '_', $bibkey);

        $entry = $this->entries[$bibkey];
        if (isset($entry['options']) and !empty(preg_grep('/^skipbib *= *true/', explode(",", $entry['options'])))) {
            return;
        }

        $linkclass = 'paper';
        $divAttributes = array();

        $hrefThesis = $this->getHrefIfExists('teaching/theses/', $bibid);
        $hrefThesisSlides = $this->getHrefIfExists('teaching/thesis-slides/', $bibid);
        $hrefPapers = $this->getHrefIfExists('papers', $bibid);
        $hrefPosters = $this->getHrefIfExists('posters', $bibid);
        $hrefSlides = $this->getHrefIfExists('slides', $bibid);

        if ($hrefThesis) {
            $href = $hrefThesis;
            $entry['thesis'] = $hrefThesis;
            $linkclass = 'thesis';
        } else if ($hrefPapers) {
            $href = $hrefPapers;
            $entry['paper'] = $hrefPapers;
        } else if (isset($entry['corpus'])) {
            $href = $entry['corpus'];
            $linkclass = 'corpus';
        } else if (isset($entry['request'])) {
            $href = 'mailto:' . $entry['request'] . self::$paperRequestSubject . $bibid;
            $entry['request'] = $href;
            $linkclass = 'request';
        }

        if ($hrefPosters) {
            $entry['poster'] = $hrefPosters;
        }

        if ($hrefThesisSlides) {
            $entry['slides'] = $hrefThesisSlides;
        } else if ($hrefSlides) {
            $entry['slides'] = $hrefSlides;
        }

        $bib = '[' . $this->wrap('a', array('class' => 'bib-toggle', 'href' => '#?q=' . $bibid, 'data-target' => "bibtex-" . $bibid), 'bib') . ']';
        $copylink = '[' . $this->wrap('a', array('class' => 'copylink', 'href' => NULL), 'copylink') . ']';

        $title = "";
        $divAttributes['data-bibid'] = $bibid;
        foreach ($entry as $key => $value) {
            if ($value !== '') {
                /* Titel mit paper-Link umschließen */
                if ($key === 'title') {
                    $title = $value;
                    $divAttributes['data-title'] = str_replace('"', '', $value);
                }
                /* Kurzschreibweise des Monats mit Langform ersetzen */
                if ($key === 'month') {
                    $month = $this->wrap('span', array('class' => 'month'), self::$month_names[$entry['month']]);
                    $divAttributes['data-month'] = self::$month_names[$entry['month']];
                } else if ($key === 'author' or $key === 'editor') {
                    $divAttributes['data-' . $key] = str_replace(" and ", ",", $value);
                    $authors = explode(' and ', $value);
                    array_walk($authors, 'trim_value');
                    if (sizeof($authors) > 4) {
                        ${'short' . $key} = $authors[0] . ' et al.';
                    }
                    if (sizeof($authors) > 2) {
                        ${$key} = implode(', ', array_slice($authors, 0, -1)) . ', and ' . end($authors);
                    } else {
                        ${$key} = $value;
                    }
                } else if ($key === 'isbn') {
                    ${$key} = 'ISBN ' . $value;
                    $divAttributes['data-isbn'] = $value;
                } else if ($key === 'issn') {
                    ${$key} = 'ISSN ' . $value;
                    $divAttributes['data-issn'] = $value;
                } else if ($key === 'number') {
                    ${$key} = '(' . $value . ')';
                    $divAttributes['data-number'] = $value;
                } else if ($key === 'chapter') {
                    ${$key} = 'Chapter ';
                    $divAttributes['data-chapter'] = $value;
                    // give Chapter part of the entry a link to the paper
                    if (isset($href)) {
                        ${$key} .= $this->wrap('a', array('href' => $href, 'class' => $linkclass), $value);
                    } else {
                        ${$key} .= $value;
                    }
                } else if ($key === 'class') {
                    $divAttributes['data-class'] = $value;
                    ${$key} = $value;
                } else if ($key === 'url') {
                    ${$key} = '[' . $this->wrap('a', array('class' => 'publisher', 'href' => $value), 'publisher') . ']';
                } else if (in_array($key, array('doi', 'poster', 'slides')) || substr($key, -3) == 'url') {
                    if (substr($key, -3) == 'url') {
                      $key = substr($key, 0, strpos($key, 'url'));
                    }
                    $label = str_replace("-", " ", $key);

                    $ahref = $value;
                    if ($key == 'doi') {
                      $ahref = 'https://doi.org/' . $ahref;
                    }
                    $linkAttributes = array('class' => $key, 'href' => $ahref);
                    ${$key} = '[' . $this->wrap('a', $linkAttributes, $label) . ']';

                    if (isset($divAttributes['data-artifacts'])) {
                        $divAttributes['data-artifacts'] = $divAttributes['data-artifacts'] . ',' . $key;
                    } else {
                        $divAttributes['data-artifacts'] = $key;
                    }
                } else {
                    if (in_array($key, array('year', 'volume', 'publisher', 'booktitle', 'journal', 'series', 'school', 'date', 'type', 'keywords', 'mentor'))) {
                        $divAttributes['data-' . $key] = $value;
                    }
                    ${$key} = $this->wrap('span', array('class' => $key), $value);
                }
            }
        }

        // check for inbook, because inbook entries have a title, but the paper link should be in the chapter part
        if (isset($href) && $class != "inbook") {
            $title = $this->wrap('a', array('href' => $href, 'class' => $linkclass), $title);
        }

        $date = (isset($month) ? $month . ' ' : '') . $year;

        switch ($class) {
            case 'article':
                if (!isset($author)) { fprintf(STDERR, "WARNING: Undefined variable 'author' in " . $bibid . "\n"); }
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($journal)) { fprintf(STDERR, "WARNING: Undefined variable 'journal' in " . $bibid . "\n"); }
                if (!isset($date)) { fprintf(STDERR, "WARNING: Undefined variable 'date' in " . $bibid . "\n"); }
                $volumeString = sprintf(
                    '%s%s%s',
                    isset($volume) ? ' ' . $volume : '',
                    isset($number) ? ' ' . $number : '',
                    isset($pages) ? ' : ' . $pages : ''
                );
                $content = sprintf(
                    '%s. %s. %s,%s %s.',
                    $author,
                    $title,
                    $journal,
                    trim($volumeString) != "" ? $volumeString . "," : "",
                    $date
                );
                break;
            case 'book':
                if (!isset($author)) { fprintf(STDERR, "WARNING: Undefined variable 'author' in " . $bibid . "\n"); }
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($publisher)) { fprintf(STDERR, "WARNING: Undefined variable 'publisher' in " . $bibid . "\n"); }
                if (!isset($year)) { fprintf(STDERR, "WARNING: Undefined variable 'year' in " . $bibid . "\n"); }
                $content = sprintf(
                    '%s. %s. %s, %s.',
                    $author,
                    $title,
                    $publisher,
                    $year
                );
                break;
            case 'inbook':
                if (!isset($author)) { fprintf(STDERR, "WARNING: Undefined variable 'author' in " . $bibid . "\n"); }
                if (!isset($booktitle)) { fprintf(STDERR, "WARNING: Undefined variable 'booktitle' in " . $bibid . "\n"); }
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($pages)) { fprintf(STDERR, "WARNING: Undefined variable 'pages' in " . $bibid . "\n"); }
                if (!isset($publisher)) { fprintf(STDERR, "WARNING: Undefined variable 'publisher' in " . $bibid . "\n"); }
                if (!isset($year)) { fprintf(STDERR, "WARNING: Undefined variable 'year' in " . $bibid . "\n"); }
                $content = sprintf(
                    '%s. %s. %s, pages %s. %s.',
                    $author,
                    $booktitle,
                    $title,
                    $pages,
                    $publisher,
                    $year
                );
                break;
            case 'incollection':
                if (!isset($author)) { fprintf(STDERR, "WARNING: Undefined variable 'author' in " . $bibid . "\n"); }
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($editor)) { fprintf(STDERR, "WARNING: Undefined variable 'editor' in " . $bibid . "\n"); }
                if (!isset($booktitle)) { fprintf(STDERR, "WARNING: Undefined variable 'booktitle' in " . $bibid . "\n"); }
                if (!isset($publisher)) { fprintf(STDERR, "WARNING: Undefined variable 'publisher' in " . $bibid . "\n"); }
                if (!isset($date)) { fprintf(STDERR, "WARNING: Undefined variable 'date' in " . $bibid . "\n"); }
                $content = sprintf(
                    '%s. %s. In %s, editors, %s%s%s%s, %s. %s.',
                    $author,
                    $title,
                    $editor,
                    $booktitle,
                    isset($volume) ? (', volume ' . $volume . (isset($series) ? ' of ' : '')) : (isset($number) ? ', number ' . $number . (isset($series) ? ' in ' : '') : (isset($series) ? ', ' : '')),
                    isset($series) ? $series : '',
                    isset($pages) ? ', pages ' . $pages : '',
                    $publisher,
                    $date
                );
                break;
            case 'inproceedings':
                if (!isset($author)) { fprintf(STDERR, "WARNING: Undefined variable 'author' in " . $bibid . "\n"); }
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($booktitle)) { fprintf(STDERR, "WARNING: Undefined variable 'booktitle' in " . $bibid . "\n"); }
                if (!isset($date)) { fprintf(STDERR, "WARNING: Undefined variable 'date' in " . $bibid . "\n"); }
                $content = sprintf(
                    '%s. %s. In %s%s%s%s%s, %s.%s',
                    $author,
                    $title,
                    isset($editor) ? (isset($shorteditor) ? $shorteditor : $editor) . ', editors, ' : '',
                    $booktitle,
                    isset($volume) ? (', volume ' . $volume . (isset($series) ? ' of ' : '')) : (isset($number) ? ', number ' . $number . (isset($series) ? ' in ' : '') : (isset($series) ? ', ' : '')),
                    isset($series) ? $series : '',
                    isset($pages) ? ', pages ' . $pages : '',
                    $date,
                    isset($publisher) ? ' ' . $publisher . '.' : ''
                );
                break;
            case 'mastersthesis':
            case 'phdthesis':
                if (!isset($author)) { fprintf(STDERR, "WARNING: Undefined variable 'author' in " . $bibid . "\n"); }
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($type)) { fprintf(STDERR, "WARNING: Undefined variable 'type' in " . $bibid . "\n"); }
                if (!isset($school)) { fprintf(STDERR, "WARNING: Undefined variable 'school' in " . $bibid . "\n"); }
                if (!isset($date)) { fprintf(STDERR, "WARNING: Undefined variable 'date' in " . $bibid . "\n"); }
                $content = sprintf(
                    '%s. %s. %s, %s, %s.',
                    $author,
                    $title,
                    $type,
                    $school,
                    $date
                );
                break;
            case 'misc':
                if (!isset($author)) { fprintf(STDERR, "WARNING: Undefined variable 'author' in " . $bibid . "\n"); }
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($year)) { fprintf(STDERR, "WARNING: Undefined variable 'year' in " . $bibid . "\n"); }
                $content = sprintf(
                    '%s. %s. %s%s.',
                    $author,
                    $title,
                    isset($howpublished) ? $howpublished . ', ' : '',
                    $year
                );
                break;
            case 'proceedings':
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($date)) { fprintf(STDERR, "WARNING: Undefined variable 'date' in " . $bibid . "\n"); }
                $content = sprintf(
                    '%s%s%s%s%s, %s.',
                    isset($editor) ? $editor . ', editors. ' : '',
                    $title,
                    isset($volume) ? (', volume ' . $volume . (isset($series) ? ' of ' : '')) : (isset($number) ? ', number ' . $number . (isset($series) ? ' in ' : '. ') : (isset($series) ? ', ' : '')),
                    isset($series) ? $series : '',
                    isset($publisher) ? ', ' . $publisher : '',
                    $date
                );
                break;
            case 'techreport':
                if (!isset($author)) { fprintf(STDERR, "WARNING: Undefined variable 'author' in " . $bibid . "\n"); }
                if (!isset($title)) { fprintf(STDERR, "WARNING: Undefined variable 'title' in " . $bibid . "\n"); }
                if (!isset($date)) { fprintf(STDERR, "WARNING: Undefined variable 'date' in " . $bibid . "\n"); }
                $content = sprintf(
                    '%s. %s. %s%s%s%s.',
                    $author,
                    $title,
                    isset($type) ? $type . ' ' : '',
                    isset($number) ? $number . ', ' : '',
                    isset($institution) ? $institution . ', ' : '',
                    $date
                );
                break;
        }

        $linksMap = array();
        $linksMap['[bib]'] = $bib;
        $linksMap['[copylink]'] = $copylink;
        if (isset($doi)) { $linksMap['[doi]'] = $doi; }
        if (isset($url)) { $linksMap[preg_replace('/<[^>]*>/', '', $url)] = $url; }
        if (isset($slides)) { $linksMap['[slides]'] = $slides; }
        if (isset($poster)) { $linksMap['[poster]'] = $poster; }
        foreach ($entry as $key => $value) {
            if ($value !== '') {
                if ($key !== 'url' && substr($key, -3) === 'url') {
                    $key = substr($key, 0, strpos($key, 'url'));
                    $linksMap['[' . $key . ']'] = ${$key};
                }
            }
        }
        ksort($linksMap);
        $links = implode(' ', $linksMap);

        $divAttributes['class'] = "bib-entry " . $class;
        $bibtexArea = "<textarea id='bibtex-" . $bibid . "' class='bibtex uk-hidden' readonly>" . $entry["plain"] . "</textarea>";

        echo isset($content) ? '    ' . $this->wrap('a', array('id' => $bibkeyclean), '') . "\n" : '';
        echo isset($content) ? '    ' . $this->wrap('div', $divAttributes, $content . ' ' . $links . $bibtexArea) . "\n" : '';
    }
}
