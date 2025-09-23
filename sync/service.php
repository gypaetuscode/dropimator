<?php

$STORE_URL = $_ENV['STORE_URL'];
$WEBSERVICE_KEY = $_ENV['WEBSERVICE_KEY'];

$webService = new PrestaShopWebservice($STORE_URL, $WEBSERVICE_KEY, true);

/**
 * Extract the first available identifier from a SimpleXMLElement list.
 *
 * @param SimpleXMLElement|null $element
 */
function extractFirstId(?SimpleXMLElement $element): ?int
{
    if ($element === null) {
        return null;
    }

    if (isset($element['id']) && (string) $element['id'] !== '') {
        return (int) $element['id'];
    }

    foreach ($element as $child) {
        if (isset($child['id']) && (string) $child['id'] !== '') {
            return (int) $child['id'];
        }
    }

    return null;
}

function getBlankSchema($resource)
{
    global $webService, $STORE_URL;

    $opt = [
        'url' => $STORE_URL . "/api/$resource?schema=blank"
    ];

    $result = $webService->get($opt);

    return $result;
}

function getManufacturerByName($manufacturerName)
{
    global $webService;

    $opt = [
        'resource' => 'manufacturers',
        'filter[name]' => "[$manufacturerName]",
    ];

    $result = $webService->get($opt);

    if (!isset($result->manufacturers)) {
        return null;
    }

    return extractFirstId($result->manufacturers->manufacturer ?? null);
};

function addManufacturer($manufacturerName)
{
    global $webService;

    $blankXml = getBlankSchema('manufacturers');
    $blankXml->manufacturer->name = $manufacturerName;

    $blankXml->manufacturer->active = 1;

    $opt = [
        'resource' => 'manufacturers',
        'postXml' => $blankXml->asXML()
    ];

    $result = $webService->add($opt);

    return $result->manufacturer->id;
}

function getProductByReference($reference)
{
    global $webService;

    $opt = [
        'resource' => 'products',
        'filter[reference]' => "[$reference]"
    ];

    $result = $webService->get($opt);

    if (!isset($result->products)) {
        return null;
    }

    return extractFirstId($result->products->product ?? null);
};

function getCategoryByName($categoryName)
{
    global $webService;

    $opt = [
        'resource' => 'categories',
        'filter[name]' => "[$categoryName]"
    ];

    $result = $webService->get($opt);

    if (!isset($result->categories)) {
        return null;
    }

    return extractFirstId($result->categories->category ?? null);
}

function addProduct(
    $reference,
    $manufacturerId,
    $name,
    $retail_price,
    $description,
    $meta_tile,
    $meta_description,
    $categoryId
) {
    global $webService, $STORE_URL;

    $blankXml = getBlankSchema('products');
    $blankXml->product->reference = $reference;
    $blankXml->product->id_manufacturer = $manufacturerId;
    $blankXml->product->name = $name;
    // $blankXml->product->weight = $weight;
    $blankXml->product->price = $retail_price;
    $blankXml->product->description = $description;
    $blankXml->product->meta_title = $meta_tile;
    $blankXml->product->meta_description = $meta_description;

    $blankXml->product->show_price = 1;
    $blankXml->product->active = 1;
    $blankXml->product->state = 1;
    $blankXml->product->id_category_default = $categoryId;
    $blankXml->product->redirect_type = '301-category';
    $blankXml->product->available_for_order = 1;

    $categoryOpt = [
        'url' => $STORE_URL . "/api/categories/$categoryId"
    ];
    $categoryResult = $webService->get($categoryOpt);


    $positionInCategory = count($categoryResult->category->associations->products->product) === 0
        ? 0
        : count($categoryResult->category->associations->products->product) - 1;

    $blankXml->product->position_in_category = $positionInCategory;
    $blankXml->product->associations->categories->addChild('category')->addChild('id', $categoryId);

    $link = strtolower($name);
    $link = preg_replace("/[^a-z0-9]+/", "-", $name);
    $link = trim($link, '-');

    $blankXml->product->link_rewrite = $link;

    $opt = [
        'resource' => 'products',
        'postXml' => $blankXml->asXML()
    ];

    $result = $webService->add($opt);

    return $result->product->id;
}

function getImageByProductId($productId)
{
    global $webService, $STORE_URL;

    $opt = [
        'url' => $STORE_URL . "/api/images/products/$productId"
    ];

    try {
        $result = $webService->get($opt);
        if (!isset($result->image)) {
            return null;
        }

        return extractFirstId($result->image->declination ?? null);
    } catch (Exception $ex) {
        return null;
    }
}

function addImageToProduct($imgUrl, $productId)
{
    global $STORE_URL, $WEBSERVICE_KEY;

    $imageUrlSplit = explode('/', $imgUrl);
    $imageName = $imageUrlSplit[count($imageUrlSplit) - 1];

    $image = file_get_contents($imgUrl);
    file_put_contents($imageName, $image);

    $imageNameSplit = explode('.', $imageName);
    $imageMime = 'image/' . $imageNameSplit[count($imageNameSplit) - 1];

    $args['image'] = new CURLFile($imageName, $imageMime);
    $urlImage = $STORE_URL . "/api/images/products/$productId/";

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_HEADER, 1);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLINFO_HEADER_OUT, 1);
    curl_setopt($ch, CURLOPT_URL, $urlImage);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_USERPWD, $WEBSERVICE_KEY . ':');
    curl_setopt($ch, CURLOPT_POSTFIELDS, $args);
    curl_exec($ch);
    curl_close($ch);

    unlink($imageName);
}

function addCombination($productId, $flavourId, $weightId, $qty, $retailPrice)
{
    global $webService;

    $blankXml = getBlankSchema('combinations');
    $blankXml->combination->id_product = $productId;
    $blankXml->combination->minimal_quantity = 1;
    $blankXml->combination->associations->product_option_values->addChild('product_option_value')->addChild('id', $flavourId);
    $blankXml->combination->associations->product_option_values->addChild('product_option_value')->addChild('id', $weightId);
    $blankXml->combination->quantity = $qty;
    // $blankXml->combination->price = $retailPrice;

    $opt = [
        'resource' => 'combinations',
        'postXml' => $blankXml->asXML()
    ];

    $result = $webService->add($opt);

    return $result->combination->id;
}

function getProductOptionByName($name)
{
    global $webService;

    $opt = [
        'resource' => 'product_options',
        'filter[name]' => "[$name]",
    ];

    $result = $webService->get($opt);

    if (!isset($result->product_options)) {
        return null;
    }

    return extractFirstId($result->product_options->product_option ?? null);
}

function getProductOptionValueByName($name)
{
    global $webService;

    $opt = [
        'resource' => 'product_option_values',
        'filter[name]' => "[$name]"
    ];

    $result = $webService->get($opt);

    if (!isset($result->product_option_values)) {
        return null;
    }

    return extractFirstId($result->product_option_values->product_option_value ?? null);
}

function addProductOptionValue($productOptionId, $flavour)
{
    global $webService;

    $blankXml = getBlankSchema('product_option_values');
    $blankXml->product_option_value->id_attribute_group = $productOptionId;
    $blankXml->product_option_value->name->language['id'] = 1;
    $blankXml->product_option_value->name->language = $flavour;

    $opt = [
        'resource' => 'product_option_values',
        'postXml' => $blankXml->asXML()
    ];

    $result = $webService->add($opt);

    return $result->product_option_value->id;
}

function getStockAvailableId($productId)
{
    global $webService, $STORE_URL;

    $opt = [
        'url' => $STORE_URL . "/api/stock_availables?display=[id]&filter[id_product]=[$productId]"
    ];

    $result = $webService->get($opt);

    if (!isset($result->stock_availables)) {
        return null;
    }

    return extractFirstId($result->stock_availables->stock_available ?? null);
}

function updateQuantityWithoutCombination($productId, $qty)
{
    global $webService, $STORE_URL;

    $stockAvailableId = getStockAvailableId($productId);

    if ($stockAvailableId === null) {
        throw new RuntimeException('Unable to locate stock for product ' . $productId);
    }

    $getStockAvailableOpt = [
        'url' => $STORE_URL . "/api/stock_availables/$stockAvailableId"
    ];

    $getStockAvailableResult = $webService->get($getStockAvailableOpt);

    $getStockAvailableResult->stock_available->quantity = $qty;

    $putOpt = [
        "resource" => "stock_availables",
        "id" => $stockAvailableId,
        "putXml" => $getStockAvailableResult->asXML()
    ];

    $webService->edit($putOpt);
}

function deleteProduct($id)
{
    global $webService;

    $opt = [
        'resource' => 'products',
        'id' => $id
    ];

    $webService->delete($opt);
}

function updateQuantityWithCombination($productId, $combinationId, $qty)
{
    global $webService, $STORE_URL;

    $stockAvailableOpt = [
        'url' => $STORE_URL . "/api/stock_availables?display=[id]&filter[id_product]=$productId&filter[id_product_attribute]=$combinationId"
    ];

    $stockAvailableResult = $webService->get($stockAvailableOpt);

    if (!isset($stockAvailableResult->stock_availables)) {
        throw new RuntimeException('Unable to locate stock for product ' . $productId . ' combination ' . $combinationId);
    }

    $stockAvailableId = extractFirstId($stockAvailableResult->stock_availables->stock_available ?? null);

    if ($stockAvailableId === null) {
        throw new RuntimeException('Unable to locate stock id for product ' . $productId . ' combination ' . $combinationId);
    }

    $stockAvailableDataOpt = [
        'url' => $STORE_URL . "/api/stock_availables/$stockAvailableId"
    ];

    $stockAvailableDataResult = $webService->get($stockAvailableDataOpt);

    $stockAvailableDataResult->stock_available->quantity = $qty;

    $stockAvailableDataUpdateOpt = [
        'resource' => 'stock_availables',
        'id' => $stockAvailableId,
        'putXml' => $stockAvailableDataResult->asXML()
    ];

    $webService->edit($stockAvailableDataUpdateOpt);
}

function getCombinationByProductId($productId)
{
    global $webService;

    $opt = [
        'resource' => 'combinations',
        'filter[id_product]' => $productId
    ];

    $result = $webService->get($opt);

    if (!isset($result->combinations)) {
        return null;
    }

    return extractFirstId($result->combinations->combination ?? null);
}
